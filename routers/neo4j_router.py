from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from neo4j_connection import neo4j_connection, convert_properties

router = APIRouter(
    prefix="/neo4j",
    tags=["neo4j"],
    responses={404: {"description": "Not found"}},
)

class NodeCreate(BaseModel):
    label: str
    properties: Dict[str, Any]

class NodeResponse(BaseModel):
    id: str
    labels: List[str]
    properties: Dict[str, Any]

class RelationshipCreate(BaseModel):
    from_id: int
    to_id: int
    type: str
    properties: Optional[Dict[str, Any]] = None

class RelationshipResponse(BaseModel):
    id: str
    type: str
    start_node: str
    end_node: str
    properties: Dict[str, Any]

class QueryModel(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None

@router.post("/nodes", response_model=Dict[str, NodeResponse])
async def create_node(node_data: NodeCreate):
    """Create a new node in Neo4j"""
    try:
        with neo4j_connection.session() as session:
            result = session.run(
                f"CREATE (n:{node_data.label} $props) RETURN n",
                props=node_data.properties
            )
            record = result.single()
            if not record:
                raise HTTPException(status_code=500, detail="Failed to create node")
            
            neo4j_node = record["n"]
            
            # Convert Neo4j Node to dictionary
            node_dict = {
                "id": str(neo4j_node.id),
                "labels": list(neo4j_node.labels),
                "properties": dict(neo4j_node)
            }
            
            return {"node": node_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}", response_model=Dict[str, Any])
async def get_node(node_id: int):
    """Get a node by ID"""
    try:
        result = neo4j_connection.get_node_by_id(node_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Node with ID {node_id} not found")
        return {"node": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {str(e)}")

@router.post("/relationships", response_model=Dict[str, Any])
async def create_relationship(relationship: RelationshipCreate):
    """Create a relationship between two nodes"""
    try:
        result = neo4j_connection.create_relationship(
            relationship.from_id, 
            relationship.to_id, 
            relationship.type, 
            relationship.properties
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create relationship")
        return {"relationship": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {str(e)}")

@router.get("/graph", response_model=Dict[str, Any])
async def get_graph(limit: int = 100):
    """Get a graph with nodes and relationships"""
    try:
        result = neo4j_connection.get_graph(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {str(e)}")

@router.get("/test-connection", response_model=Dict[str, Any])
async def test_connection():
    """Test the Neo4j connection"""
    try:
        # Execute a simple query to test the connection
        result = neo4j_connection.execute_query("RETURN 'Connected!' AS message")
        return {"status": "success", "message": result[0]["message"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j connection failed: {str(e)}")

@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users():
    """Get all users from Neo4j"""
    try:
        with neo4j_connection.session() as session:
            result = session.run(
                """
                MATCH (u:User)
                RETURN u
                """
            )
            
            users = []
            for record in result:
                user = record["u"]
                users.append({
                    "id": user.id,
                    "properties": convert_properties(dict(user))
                })
            
            return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {str(e)}") 