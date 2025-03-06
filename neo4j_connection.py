from neo4j import GraphDatabase
from neo4j.time import DateTime
from contextlib import contextmanager
import os
from typing import Dict, List, Any, Optional
import datetime

# Get Neo4j connection details from environment variables
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Helper function to convert Neo4j types to Python types
def convert_neo4j_to_python(value):
    if isinstance(value, DateTime):
        return value.to_native().isoformat()
    return value

# Helper function to convert Neo4j node/relationship properties
def convert_properties(props):
    return {k: convert_neo4j_to_python(v) for k, v in props.items()}

class Neo4jConnection:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
    
    @contextmanager
    def session(self):
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self):
        self.driver.close()
    
    def get_node_by_id(self, node_id):
        with self.session() as session:
            result = session.run("MATCH (n) WHERE id(n) = $id RETURN n", id=node_id)
            record = result.single()
            if not record:
                return None
            
            node = record["n"]
            return {
                "id": node.id,
                "labels": list(node.labels),
                "properties": convert_properties(dict(node))
            }
    
    def create_relationship(self, from_id, to_id, rel_type, properties=None):
        if properties is None:
            properties = {}
            
        with self.session() as session:
            result = session.run(
                """
                MATCH (a), (b) 
                WHERE id(a) = $from_id AND id(b) = $to_id
                CREATE (a)-[r:`{}`]->(b)
                SET r = $props
                RETURN r
                """.format(rel_type),
                from_id=from_id,
                to_id=to_id,
                props=properties
            )
            record = result.single()
            if not record:
                return None
                
            rel = record["r"]
            return {
                "id": rel.id,
                "type": rel.type,
                "start_node": rel.start_node.id,
                "end_node": rel.end_node.id,
                "properties": dict(rel)
            }
    
    def get_graph(self, limit=100):
        with self.session() as session:
            result = session.run(
                """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, r, m
                LIMIT $limit
                """,
                limit=limit
            )
            
            nodes = {}
            relationships = []
            
            for record in result:
                # Process start node
                if record["n"] and record["n"].id not in nodes:
                    node = record["n"]
                    nodes[node.id] = {
                        "id": node.id,
                        "labels": list(node.labels),
                        "properties": convert_properties(dict(node))
                    }
                
                # Process end node if exists
                if record["m"] and record["m"].id not in nodes:
                    node = record["m"]
                    nodes[node.id] = {
                        "id": node.id,
                        "labels": list(node.labels),
                        "properties": convert_properties(dict(node))
                    }
                
                # Process relationship if exists
                if record["r"]:
                    rel = record["r"]
                    relationships.append({
                        "id": rel.id,
                        "type": rel.type,
                        "source": rel.start_node.id,
                        "target": rel.end_node.id,
                        "properties": convert_properties(dict(rel))
                    })
            
            return {
                "nodes": list(nodes.values()),
                "relationships": relationships
            }
    
    def execute_query(self, query, params=None):
        if params is None:
            params = {}
            
        with self.session() as session:
            result = session.run(query, params)
            return [record.data() for record in result]

# Create a singleton instance
neo4j_connection = Neo4jConnection(URI, USERNAME, PASSWORD) 