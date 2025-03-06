from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import subprocess
from datetime import datetime
import uvicorn
import tempfile
from dotenv import load_dotenv
from routers import neo4j_router  # When running from server directory
from neo4j import GraphDatabase
from pydantic import BaseModel
from typing import Optional

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configure CORS to allow requests from your React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Your React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the Neo4j router
app.include_router(neo4j_router.router)

# Create the output directory if it doesn't exist
OUTPUT_DIR = "data/webcam_video_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")
driver = GraphDatabase.driver(uri, auth=(user, password))

class RelationshipCreate(BaseModel):
    from_id: str
    to_id: str
    type: str
    properties: Optional[dict] = {}

class NodeCreate(BaseModel):
    label: str
    properties: dict

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        # Create a temporary file to store the uploaded webm
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
            # Copy uploaded file to the temporary file
            shutil.copyfileobj(file.file, temp_webm)
            temp_webm_path = temp_webm.name
        
        # Create a unique filename with timestamp for the output mp4
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"webcam_recording_{timestamp}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Convert webm to mp4 using ffmpeg
        try:
            # Run ffmpeg command to convert the file with higher quality settings
            subprocess.run([
                'ffmpeg',
                '-i', temp_webm_path,
                '-c:v', 'libx264',     # Use H.264 codec for video
                '-preset', 'slow',     # Slower preset = better quality
                '-crf', '18',          # Lower CRF value = higher quality (18 is high quality, 23 is default)
                '-c:a', 'aac',         # Use AAC codec for audio
                '-b:a', '320k',        # Higher audio bitrate
                '-ar', '48000',        # Audio sample rate (CD quality)
                '-af', 'highpass=f=80, lowpass=f=16000', # Audio filter to remove underwater effect
                '-movflags', '+faststart',  # Optimize for web streaming
                output_path
            ], check=True)
            
            # Clean up the temporary webm file
            os.unlink(temp_webm_path)
            
            return {"filename": output_filename, "status": "success"}
        except subprocess.CalledProcessError as e:
            return {"error": f"FFmpeg conversion failed: {str(e)}", "status": "failed"}
        
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@app.get("/")
async def root():
    return {"message": "Neo4j API is running"}

@app.get("/api/users/{email}")
async def get_user_node(email: str):
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User {value: $email}) RETURN u",
            email=email
        )
        user = result.single()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        node = user['u']
        return {
            "id": node.id,
            "properties": dict(node)
        }

@app.post("/api/relationships")
async def create_relationship(relationship: RelationshipCreate):
    try:
        with driver.session() as session:
            # Create the query with the relationship type directly in the string
            query = f"""
                MATCH (from) WHERE from.uiNodeId = $from_id
                MATCH (to) WHERE to.uiNodeId = $to_id
                CREATE (from)-[r:{relationship.type}]->(to)
                SET r += $properties
                RETURN r
                """
            result = session.run(
                query,
                from_id=relationship.from_id,
                to_id=relationship.to_id,
                properties=relationship.properties
            )
            return {"message": "Relationship created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/nodes")
async def create_node(node: NodeCreate):
    try:
        with driver.session() as session:
            result = session.run(
                f"""
                CREATE (n:{node.label} $properties)
                RETURN n
                """,
                properties=node.properties
            )
            created_node = result.single()['n']
            return {
                "node": {
                    "id": created_node.id,
                    "properties": dict(created_node)
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/smart-goals/{user_email}")
async def get_user_smart_goals(user_email: str):
    try:
        with driver.session() as session:
            query = """
            MATCH (u:User {value: $email})-[r1:HAS_GOAL]->(g:Goal)
            MATCH (g)-[r2:BELONGS_TO_USER]->(u)
            RETURN g, r1, r2
            """
            result = session.run(query, email=user_email)
            
            goals = []
            relationships = []
            for record in result:
                goal = record['g']
                has_rel = record['r1']
                belongs_rel = record['r2']
                
                goals.append({
                    "id": goal.id,
                    "properties": dict(goal)
                })
                
                relationships.extend([
                    {
                        "id": str(has_rel.id),
                        "type": "HAS_GOAL",
                        "from_node": {"id": has_rel.nodes[0].id, "properties": dict(has_rel.nodes[0])},
                        "to_node": {"id": has_rel.nodes[1].id, "properties": dict(has_rel.nodes[1])}
                    },
                    {
                        "id": str(belongs_rel.id),
                        "type": "BELONGS_TO_USER",
                        "from_node": {"id": belongs_rel.nodes[0].id, "properties": dict(belongs_rel.nodes[0])},
                        "to_node": {"id": belongs_rel.nodes[1].id, "properties": dict(belongs_rel.nodes[1])}
                    }
                ])
            
            return {"goals": goals, "relationships": relationships}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/{user_email}")
async def get_user_metrics(user_email: str):
    try:
        with driver.session() as session:
            query = """
            MATCH (u:User {value: $email})-[r1:HAS_METRIC]->(m:Metric)
            MATCH (m)-[r2:BELONGS_TO_USER]->(u)
            RETURN m, r1, r2
            """
            result = session.run(query, email=user_email)
            
            metrics = []
            relationships = []
            for record in result:
                metric = record['m']
                has_rel = record['r1']
                belongs_rel = record['r2']
                
                metrics.append({
                    "id": metric.id,
                    "properties": dict(metric)
                })
                
                relationships.extend([
                    {
                        "id": str(has_rel.id),
                        "type": "HAS_METRIC",
                        "from_node": {"id": has_rel.nodes[0].id, "properties": dict(has_rel.nodes[0])},
                        "to_node": {"id": has_rel.nodes[1].id, "properties": dict(has_rel.nodes[1])}
                    },
                    {
                        "id": str(belongs_rel.id),
                        "type": "BELONGS_TO_USER",
                        "from_node": {"id": belongs_rel.nodes[0].id, "properties": dict(belongs_rel.nodes[0])},
                        "to_node": {"id": belongs_rel.nodes[1].id, "properties": dict(belongs_rel.nodes[1])}
                    }
                ])
            
            return {"metrics": metrics, "relationships": relationships}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 