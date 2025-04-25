# Deploying Tunesmith to Google Kubernetes Engine (GKE)

This guide provides step-by-step instructions for deploying the Tunesmith application to a Google Kubernetes Engine (GKE) cluster.

## Prerequisites

1. Google Cloud Platform (GCP) account with billing enabled
2. Google Cloud SDK (gcloud) installed and configured
3. Docker installed locally
4. kubectl installed locally
5. A domain name purchased and ready to configure

## Setup GCP Project and GKE Cluster

If you haven't already created a GKE cluster, you can do so using the following commands:

```bash
# Set your project ID
PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable container.googleapis.com

# Create a GKE cluster
gcloud container clusters create tunesmith-cluster \
  --zone us-central1-a \
  --num-nodes 1 \
  --machine-type e2-medium
```

## Prepare Environment Variables and Secrets

1. Create a copy of the secrets template for your actual deployment:

```bash
cp kubernetes/secrets.yaml kubernetes/secrets-prod.yaml
```

2. Prepare your secret values by Base64 encoding them:

```bash
echo -n "your-openai-api-key" | base64
echo -n "your-spotify-client-id" | base64
echo -n "your-spotify-client-secret" | base64
echo -n "your-flask-secret-key" | base64
```

3. Edit the `kubernetes/secrets-prod.yaml` file with your Base64 encoded values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tunesmith-secrets
type: Opaque
data:
  openai-api-key: BASE64_ENCODED_OPENAI_API_KEY
  spotify-client-id: BASE64_ENCODED_SPOTIFY_CLIENT_ID
  spotify-client-secret: BASE64_ENCODED_SPOTIFY_CLIENT_SECRET
  flask-secret-key: BASE64_ENCODED_FLASK_SECRET_KEY
```

4. Update the following files with your specific values:

- `kubernetes/deployment.yaml`: Replace `YOUR_GCP_PROJECT_ID` with your actual GCP project ID
- `kubernetes/ingress.yaml`: Replace `YOUR_DOMAIN` with your actual domain name
- `kubernetes/certificate.yaml`: Replace `YOUR_DOMAIN` with your actual domain name
- `deploy-to-gke.sh`: Update the configuration variables at the top of the script

5. Update the Spotify callback URL in your Spotify Developer Dashboard:
   - Add `https://YOUR_DOMAIN/callback` as an authorized redirect URI (you'll need to update this after you know your actual domain setup)

## Platform Compatibility (Important for Mac users)

If you're using an ARM-based Mac (M1/M2/M3), you must ensure your Docker build targets the correct platform for GKE:

1. The Dockerfile already includes the platform specification:
```
FROM --platform=linux/amd64 python:3.11-slim
```

2. The deploy script should use the platform flag when building:
```bash
docker build --platform linux/amd64 -t "gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest" .
```

This ensures compatibility between ARM-based development machines and x86-based GKE environments.

## Deploy the Application

1. Make the deployment script executable:

```bash
chmod +x deploy-to-gke.sh
```

2. Run the deployment script:

```bash
./deploy-to-gke.sh
```

## Get the External IP for DNS Configuration

After deployment, get the external IP address assigned to your ingress:

```bash
kubectl get ingress tunesmith-ingress
```

Note the IP address in the ADDRESS column (e.g., 34.120.15.123). You'll need this for DNS configuration.

## DNS Configuration

Once you have the external IP from your deployment:

1. Go to your domain registrar's DNS management page (e.g., GoDaddy, Namecheap)

2. Create a single A record pointing to your ingress IP:
   - Type: A
   - Name: @ (or leave blank for root domain)
   - Value: [Your External IP from `kubectl get ingress`]
   - TTL: 1 hour

3. Remove any conflicting records:
   - Delete any CNAME records pointing to domain parking pages
   - Disable any domain forwarding services

4. Optionally add a www subdomain:
   - Type: CNAME
   - Name: www
   - Value: your-domain.com
   - TTL: 1 hour

5. Wait for DNS propagation (can take anywhere from minutes to 48 hours)

## Verify Deployment

1. Check if all resources are created successfully:

```bash
kubectl get all
kubectl get ingress
kubectl get managedcertificate
```

2. Monitor the status of your ManagedCertificate:

```bash
kubectl describe managedcertificate tunesmith-certificate
```

3. Once the ingress is created and the certificate is provisioned (which may take 15-30 minutes), access your application at your configured domain.

## Troubleshooting

If you encounter issues with the deployment:

1. Check pod logs:

```bash
kubectl get pods
kubectl logs [pod-name]
```

2. Check service status:

```bash
kubectl describe service tunesmith
```

3. Check ingress status:

```bash
kubectl describe ingress tunesmith-ingress
```

4. If the certificate fails to provision, try recreating it with a new name:
```bash
kubectl delete managedcertificate tunesmith-certificate
kubectl apply -f - <<EOF
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: tunesmith-certificate-new
spec:
  domains:
  - YOUR_DOMAIN
EOF
kubectl patch ingress tunesmith-ingress --type=json -p='[{"op": "replace", "path": "/metadata/annotations/networking.gke.io~1managed-certificates", "value": "tunesmith-certificate-new"}]'
```

## Updating the Application

To update the application after making changes:

1. Rebuild and push the Docker image:

```bash
docker build -t gcr.io/$PROJECT_ID/tunesmith:latest .
docker push gcr.io/$PROJECT_ID/tunesmith:latest
```

2. Restart the deployment:

```bash
kubectl rollout restart deployment tunesmith
``` 