# Edna <> amoCRM Integration Service

This service acts as a middleware to enable two-way communication between the edna Pulse messaging platform and amoCRM Chats. It routes messages, media, and status updates between the two systems.

## Features

- **Two-way message routing**: Messages from clients in edna are delivered to amoCRM chats, and messages from agents in amoCRM are sent to clients via edna.
- **Media support**: Handles images and file attachments.
- **Status synchronization**: Synchronizes message statuses (sent, delivered, read) from edna to amoCRM.
- **Clean Architecture**: Built using principles of Clean Architecture for maintainability and testability.
- **Containerized**: Ready to be deployed as a Docker container.

## Architecture

The application follows a classic Clean Architecture structure, separating concerns into four main layers:

- `domain`: Contains core business logic, entities (e.g., `Message`), and interfaces (ports).
- `use_cases`: Orchestrates the flow of data between the domain and infrastructure layers.
- `infrastructure`: Implements external-facing components like HTTP clients and repositories.
- `presentation`: Exposes the application to the outside world via a REST API (FastAPI), defining schemas and handling web requests.

## API Endpoints

The service exposes the following endpoints. For detailed request/response models, refer to the auto-generated OpenAPI documentation at `/docs` when the service is running.

### Health Check

- `GET /health`
  - **Description**: Checks if the service is running and available.
  - **Success Response (200 OK)**:
    ```json
    {
      "status": "ok"
    }
    ```

### Webhooks

- `POST /webhooks/edna`
  - **Description**: Receives incoming messages and status updates from the edna Pulse platform.
  - **Request Body**: Can be one of two types: `EdnaIncomingMessage` or `EdnaStatusUpdate`.
  - **Success Response (200 OK)**:
    ```json
    {
      "code": "ok"
    }
    ```

- `POST /webhooks/amocrm`
  - **Description**: Receives new messages sent by agents from an amoCRM chat.
  - **Request Body**: `AmoIncomingWebhook`.
  - **Success Response (200 OK)**:
    ```json
    {
      "code": "ok"
    }
    ```

## Configuration

The service is configured using environment variables. Create a `.env` file in the project root to manage them.

| Variable | Description | Default Value |
| --- | --- | --- |
| `EDNA_API_KEY` | Your API key for edna Pulse. | `your_edna_api_key` |
| `AMOCRM_BASE_URL` | The base URL of your amoCRM instance (e.g., `https://your_subdomain.amocrm.ru`). | `https://your_subdomain.amocrm.ru` |
| `AMOCRM_TOKEN` | Your Bearer token for the amoCRM API. | `your_amocrm_token` |

## Setup and Running

The easiest way to run the service is using Docker.

1.  **Create a `.env` file** in the project root with the necessary configuration:
    ```env
    EDNA_API_KEY=your_key_from_edna
    AMOCRM_BASE_URL=https://youraccount.amocrm.ru
    AMOCRM_TOKEN=your_amocrm_api_token
    ```

2.  **Build the Docker image**:
    ```bash
    docker build -t edna-amocrm-integration . -f src/Dockerfile
    ```

3.  **Run the container**:
    ```bash
    docker run -d --env-file .env -p 8000:8000 --name edna-amocrm-app edna-amocrm-integration
    ```
The service will be available at `http://localhost:8000`.

## Webhook Payload Examples

### Edna: Incoming Message

```json
{
    "id": "msg-12345",
    "imType": "whatsapp",
    "subject": "79001234567",
    "text": "Hello, I have a question!",
    "fromClient": true
}
```

### Edna: Status Update

```json
{
    "id": "msg-abcde",
    "status": "read"
}
```

### amoCRM: Incoming Webhook

```json
{
    "message": {
        "id": "chat-msg-67890",
        "text": "Hello, how can I help you?",
        "date": 1678886400
    },
    "sender": {
        "id": "user-1",
        "name": "John Doe"
    },
    "conversation": {
        "id": "chat-xyz"
    },
    "account": {
        "id": "acc-123",
        "subdomain": "youraccount"
    }
}
```
