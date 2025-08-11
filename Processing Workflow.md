# Processing Workflow

## Step 1: Job Initiation

User creates shelving job via API
POST /api/jobs/create
{
"job_type": "shelving",
"parameters": {
"batch_size": 20,
"max_emails": 100,
"enable_vector_storage": true,
"similarity_threshold": 0.7
}
}

## Step 2: Job Setup & Gmail Connection

async def process_shelving_job(self, job_id: str, parameters: dict): # 1. Initialize Gmail organizer (if not exists)
if not self.gmail_organizer:
self.gmail_organizer = GmailAIOrganizer(credentials_file=creds_path)
auth_success = self.gmail_organizer.authenticate() # OAuth token validation

    # 2. Get batch configuration
    batch_size = parameters.get('batch_size', 20)  # Process 20 emails at a time
    max_emails = parameters.get('max_emails', 100) # Total limit

## Step 3: Gmail API Batch Retrieval

## Step 4: Batch Processing Loop
