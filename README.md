FastAPI Neo4j Video Processing API
A FastAPI application that handles video uploads, processing, and Neo4j graph database integration.
Features
Video upload and processing
Neo4j graph database integration
RESTful API endpoints for data management
Setup
Clone the repository
Install dependencies: pip install -r requirements.txt
Create a .env file with Neo4j connection details:
neo4j
Running the Application
Start the server: python main.py
The API will be available at http://localhost:8000
API documentation is available at:
http://localhost:8000/docs
http://localhost:8000/redoc
API Endpoints
Video upload: POST /upload-video
Neo4j operations: Various endpoints under /neo4j/
Development
Run with auto-reload: uvicorn main:app --reload