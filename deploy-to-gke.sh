#!/bin/bash
set -e

# Configuration
PROJECT_ID="coms6998amc"
IMAGE_NAME="tunesmith"
CLUSTER_NAME="tunesmith-cluster"
REGION="us-central1"
ZONE="us-central1-a"

# Build the Docker image with platform specification
echo "Building Docker image..."
docker build --platform linux/amd64 -t "gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest" .

# Push the image to Google Container Registry
echo "Pushing image to GCR..."
docker push "gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# Configure kubectl to use the GKE cluster
echo "Configuring kubectl..."
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${ZONE} --project ${PROJECT_ID}

# Check for production secrets file
SECRETS_FILE="kubernetes/secrets-prod.yaml"
if [ ! -f "$SECRETS_FILE" ]; then
    echo "Error: $SECRETS_FILE not found!"
    echo "Please create this file with your actual secrets before deploying."
    echo "You can use kubernetes/secrets.yaml as a template."
    exit 1
fi

# Apply Kubernetes configurations
echo "Applying Kubernetes configurations..."
kubectl apply -f ${SECRETS_FILE}
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/certificate.yaml
kubectl apply -f kubernetes/ingress.yaml

echo "Deployment complete!"
echo "It may take a few minutes for the ingress and certificate to be provisioned." 