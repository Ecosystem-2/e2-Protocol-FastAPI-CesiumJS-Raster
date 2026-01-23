# Google Cloud Storage Credentials Setup

This guide explains how to generate and configure Google Cloud Storage service account credentials for the HOB FastAPI project.

## Prerequisites

- Google Cloud account
- Access to create service accounts in your GCP project
- Project created in Google Cloud Console

## Step-by-Step Guide

### 1. Access Google Cloud Console

- Navigate to [Google Cloud Console](https://console.cloud.google.com/)
- Select your project (or create a new one if needed)

### 2. Create Service Account

1. In the left sidebar, go to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Enter a name (e.g., `climate-tiles-service`)
4. Optionally add a description (e.g., "Service account for HOB FastAPI climate tile storage")
5. Click **Create and Continue**

### 3. Grant Storage Permissions

Choose the appropriate role based on your needs:

**Option A: Full Storage Access (Recommended for Development)**
- Add role: **Storage Admin**
- This allows full control over GCS buckets and objects

**Option B: Object-Only Access (More Restrictive)**
- Add role: **Storage Object Admin**
- This only allows managing objects, not buckets

After selecting the role:
1. Click **Continue**
2. Skip the "Grant users access to this service account" section
3. Click **Done**

### 4. Generate JSON Key

1. In the Service Accounts list, click on the service account you just created
2. Click on the **Keys** tab
3. Click **Add Key** → **Create New Key**
4. Select **JSON** format
5. Click **Create**
6. The JSON key file will download automatically to your computer

### 5. Configure the Project

**Save the Credentials File:**

```bash
# Navigate to your project root
cd HOB-FastAPI.Python

# Create data directory if it doesn't exist
mkdir -p data

# Move the downloaded JSON file to the project
# Replace 'your-project-xxxxx.json' with your actual filename
mv ~/Downloads/your-project-xxxxx.json ./data/gcs_credentials.json

# Verify the file is in place
ls -la ./data/gcs_credentials.json
```

**Update Environment Variables:**

Add or update the following in your `.env` file:

```bash
GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json
GCS_BUCKET=climate-tiles-cluster      # Your bucket name
GCS_PREFIX=uploads                    # Storage prefix/folder
```

Or append to `.env` using command line:

```bash
echo "GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json" >> .env
```

### 6. Create GCS Bucket

If you haven't created a bucket yet:

**Using gcloud CLI:**

```bash
# Install gcloud if needed: https://cloud.google.com/sdk/docs/install

# Create bucket with regional storage
gcloud storage buckets create gs://climate-tiles-cluster \
  --location=us-central1 \
  --uniform-bucket-level-access

# Or for multi-regional storage
gcloud storage buckets create gs://climate-tiles-cluster \
  --location=us \
  --uniform-bucket-level-access
```

**Using Google Cloud Console:**

1. Go to **Cloud Storage** → **Buckets**
2. Click **Create Bucket**
3. Enter bucket name (e.g., `climate-tiles-cluster`)
4. Choose location type and region
5. Select **Uniform** access control
6. Click **Create**

### 7. Verify Setup

Test that the credentials work:

```bash
# Using gcloud with the service account
gcloud auth activate-service-account --key-file=./data/gcs_credentials.json

# List buckets to verify access
gcloud storage buckets list

# Or test uploading a file
echo "test" > test.txt
gcloud storage cp test.txt gs://climate-tiles-cluster/test.txt
gcloud storage rm gs://climate-tiles-cluster/test.txt
rm test.txt
```

## Security Best Practices

### 1. Never Commit Credentials to Version Control

The `.gitignore` file already includes:
```
data/gcs_credentials.json
*.json  # in data/ directory context
```

Always verify before committing:
```bash
git status
# Ensure gcs_credentials.json is not listed
```

### 2. Use Minimum Required Permissions

For production environments:
- Use **Storage Object Admin** instead of **Storage Admin** if you don't need to create/delete buckets
- Consider using **Storage Object Creator** if you only need to upload files
- Apply bucket-level IAM policies for finer control

### 3. Rotate Keys Regularly

1. Create a new key for the service account
2. Update the credentials file
3. Test that the new key works
4. Delete the old key from the service account

```bash
# List keys for a service account
gcloud iam service-accounts keys list \
  --iam-account=climate-tiles-service@your-project.iam.gserviceaccount.com

# Delete an old key
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=climate-tiles-service@your-project.iam.gserviceaccount.com
```

### 4. Use Environment-Specific Credentials

For different environments, use separate service accounts:
- **Development**: `climate-tiles-dev@project.iam.gserviceaccount.com`
- **Staging**: `climate-tiles-staging@project.iam.gserviceaccount.com`
- **Production**: `climate-tiles-prod@project.iam.gserviceaccount.com`

### 5. Monitor Service Account Usage

Regularly check the service account activity:
1. Go to **IAM & Admin** → **Service Accounts**
2. Click on your service account
3. View the **Permissions** and **Keys** tabs
4. Check **Audit Logs** for unusual activity

## Troubleshooting

### Error: "Could not automatically determine credentials"

**Cause**: Environment variable not set or file path is incorrect

**Solution**:
```bash
# Verify the environment variable is set
echo $GOOGLE_APPLICATION_CREDENTIALS

# Check file exists and is readable
cat ./data/gcs_credentials.json | jq .

# Ensure the path in .env is correct (absolute or relative to project root)
```

### Error: "Permission denied" when accessing bucket

**Cause**: Service account lacks proper permissions

**Solution**:
1. Go to **Cloud Storage** → **Buckets** → Your Bucket
2. Click **Permissions** tab
3. Add the service account email with **Storage Object Admin** role
4. Or update IAM policy at project level

### Error: "Invalid JSON" when loading credentials

**Cause**: Corrupted or incomplete credentials file

**Solution**:
1. Validate JSON syntax: `cat ./data/gcs_credentials.json | jq .`
2. If invalid, re-download the key from Google Cloud Console
3. Ensure no extra characters were added during copy/paste

### Bucket not found

**Cause**: Bucket doesn't exist or name is incorrect

**Solution**:
```bash
# List all buckets you have access to
gcloud storage buckets list

# Verify bucket name in .env matches exactly
grep GCS_BUCKET .env
```

## Additional Resources

- [Google Cloud Service Accounts Documentation](https://cloud.google.com/iam/docs/service-accounts)
- [GCS Authentication Best Practices](https://cloud.google.com/storage/docs/authentication)
- [IAM Roles for Cloud Storage](https://cloud.google.com/storage/docs/access-control/iam-roles)
- [Google Cloud SDK Installation](https://cloud.google.com/sdk/docs/install)

## Quick Reference

```bash
# Environment variables needed in .env
GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json
GCS_BUCKET=climate-tiles-cluster
GCS_PREFIX=uploads

# Test credentials
gcloud auth activate-service-account --key-file=./data/gcs_credentials.json
gcloud storage buckets list

# Create bucket
gcloud storage buckets create gs://bucket-name --location=us-central1

# View service account keys
gcloud iam service-accounts keys list --iam-account=SERVICE_ACCOUNT_EMAIL
```
