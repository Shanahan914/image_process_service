# Image Processing API

This project is a FastAPI application that allows users to upload images, apply transformations, and retrieve the processed images. It utilizes RabbitMQ for handling image transformation tasks asynchronously and PostgreSQL for data storage.

Completed as a solution to roadmapsh image processing project - https://roadmap.sh/projects/image-processing-service

Next steps for this are to add rate limiting and a cache for transformed images. 

## Features

- User registration and authentication
- Image upload and retrieval
- Asynchronous image processing using RabbitMQ
- User-specific image transformations
- Pagination and search functionality for images

## Technologies Used

- FastAPI
- SQLModel
- PostgreSQL
- RabbitMQ
- Boto3 (for AWS S3 integration)
- Docker

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/image_processing_api.git
   cd image_processing_api
   ```

2. Create a `.env` file in the root directory with the following content:
   ```
   DATABASE_URL=postgresql://imager:password@db/mage_processing
   S3_BUCKET_NAME=your_s3_bucket_name
   AWS_ACCESS_KEY_ID=your_access_key_id
   REGION = "e.g. eu-north-1"
   AWS_SECRET_ACCESS_KEY=your_secret_access_key
   PG_OWNER = 'db owner'
   PG_PASSWORD = ''db password
   ```

3. Build and run the Docker containers:
   ```bash
   docker-compose up --build
   ```

4. Access the API at `http://localhost:8000`.

## Usage

### User Registration

POST `/users/`
```json
{
  "email": "user@example.com",
  "plain_password": "yourpassword"
}
```

### JWT Token

POST `/users/`
```json
{
  "username": "user@example.com", #use email
  "password": "yourpassword"
}
```

### Upload Image

POST `/images/upload`
```json
{
  "image": "base64_encoded_image_data"
}
```

### Transform Image

POST `/images/:id/transform`
```json
{
  {
  "transformations": {
    "resize": {
      "width": 0,
      "height": 0
    },
    "crop": {
      "width": 0,
      "height": 0,
      "x": 0,
      "y": 0
    },
    "rotate": 0,
    "filters": {
      "grayscale": true
    }
  }
}
}
```

### List Images (metadata)

GET `/images`
- Query parameters:
  - `skip`: Number of records to skip (default: 0)
  - `limit`: Number of records to return (default: 10)
  - `q`: Search query for image filename

### Get Images (image)

GET `/images/:id`

## Running Locally

To run the application locally without Docker:

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the FastAPI application:
   ```bash
   uvicorn app.main:app --reload
   ```

## License

This project is licensed under the MIT License.
