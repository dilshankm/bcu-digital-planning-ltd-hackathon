# GitHub Secrets Configuration for AWS Fargate Deployment

## Required GitHub Secrets

You need to add these secrets to your GitHub repository:

**Settings → Secrets and variables → Actions → New repository secret**

---

## 1. AWS Credentials

### `AWS_ACCESS_KEY_ID`
- **Description**: Your AWS IAM access key ID
- **How to get**: 
  1. Go to AWS Console → IAM → Users
  2. Create a new user or use existing user
  3. Attach policy: `AmazonECS_FullAccess` and `AmazonEC2ContainerRegistryFullAccess`
  4. Go to Security credentials → Create access key
- **Example**: `AKIAIOSFODNN7EXAMPLE`

### `AWS_SECRET_ACCESS_KEY`
- **Description**: Your AWS IAM secret access key
- **How to get**: Same as above (shown only once when creating access key)
- **Example**: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

### `AWS_REGION`
- **Description**: AWS region where your ECS cluster is located
- **Example**: `us-east-1` or `eu-west-1` or `ap-southeast-1`

---

## 2. Docker Hub Credentials

### `DOCKER_USERNAME`
- **Description**: Your Docker Hub username
- **How to get**: Your Docker Hub account username
- **Example**: `dilshankm`

### `DOCKER_PASSWORD`
- **Description**: Your Docker Hub password or access token (recommended)
- **How to get**: 
  1. Go to Docker Hub → Account Settings → Security
  2. Create a new access token
- **Example**: `dckr_pat_abc123xyz...`

---

## 3. ECS Configuration

### `ECS_CLUSTER_NAME`
- **Description**: Name of your ECS cluster
- **How to create**:
  ```bash
  aws ecs create-cluster --cluster-name graphrag-hackathon-cluster
  ```
- **Example**: `graphrag-hackathon-cluster`

### `ECS_SERVICE_NAME`
- **Description**: Name of your ECS service
- **Note**: Will be created if it doesn't exist
- **Example**: `graphrag-hackathon-service`

### `ECS_EXECUTION_ROLE_ARN`
- **Description**: ARN of the ECS task execution role
- **How to create**:
  ```bash
  # Create trust policy file
  cat > ecs-trust-policy.json <<EOF
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }
  EOF
  
  # Create execution role
  aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://ecs-trust-policy.json
  
  # Attach managed policy
  aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
  
  # Get the ARN
  aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.Arn' --output text
  ```
- **Example**: `arn:aws:iam::123456789012:role/ecsTaskExecutionRole`

### `ECS_TASK_ROLE_ARN`
- **Description**: ARN of the ECS task role (for application permissions)
- **How to create**:
  ```bash
  # Create task role (similar to above)
  aws iam create-role \
    --role-name ecsTaskRole \
    --assume-role-policy-document file://ecs-trust-policy.json
  
  # Get the ARN
  aws iam get-role --role-name ecsTaskRole --query 'Role.Arn' --output text
  ```
- **Example**: `arn:aws:iam::123456789012:role/ecsTaskRole`

---

## 4. Application Environment Variables

### `OPENAI_API_KEY`
- **Description**: Your OpenAI API key for GPT-3.5-turbo
- **How to get**: https://platform.openai.com/api-keys
- **Example**: `sk-proj-abc123...`

### `NEO4J_URI`
- **Description**: Neo4j database connection URI
- **Example**: `neo4j+s://xxxxx.databases.neo4j.io` or `bolt://your-neo4j-host:7687`

### `NEO4J_USERNAME`
- **Description**: Neo4j database username
- **Example**: `neo4j`

### `NEO4J_PASSWORD`
- **Description**: Neo4j database password
- **Example**: Your Neo4j password

---

## Quick Setup Commands

### 1. Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name graphrag-hackathon-cluster
```

### 2. Create CloudWatch Log Group
```bash
aws logs create-log-group --log-group-name /ecs/graphrag-hackathon
```

### 3. Create ECS Service (after first deployment)
```bash
# Get your VPC ID
VPC_ID=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)

# Get subnet IDs
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text | tr '\t' ',')

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name graphrag-sg \
  --description "Security group for GraphRAG app" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Allow inbound traffic on port 8080
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0

# Create ECS service (will be done automatically by GitHub Actions on first run)
```

---

## GitHub Secrets Summary (Copy this list)

Here's the complete list to add to GitHub Secrets:

```
AWS_ACCESS_KEY_ID=<your-aws-access-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret-key>
AWS_REGION=us-east-1

DOCKER_USERNAME=dilshankm
DOCKER_PASSWORD=<your-docker-token>

ECS_CLUSTER_NAME=graphrag-hackathon-cluster
ECS_SERVICE_NAME=graphrag-hackathon-service
ECS_EXECUTION_ROLE_ARN=<your-execution-role-arn>
ECS_TASK_ROLE_ARN=<your-task-role-arn>

OPENAI_API_KEY=<your-openai-key>
NEO4J_URI=<your-neo4j-uri>
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

---

## Additional Notes

1. **First Deployment**: You may need to manually create the ECS service first, or modify the workflow to create it automatically.

2. **Load Balancer** (Optional): If you want public access via HTTPS:
   - Create an Application Load Balancer (ALB)
   - Create a target group pointing to port 8080
   - Update the ECS service to use the load balancer

3. **Cost Optimization**:
   - The task uses 1 vCPU and 2GB memory (adjust in workflow if needed)
   - Consider using AWS Spot instances for Fargate to reduce costs

4. **Monitoring**: Access logs at:
   ```
   AWS Console → CloudWatch → Log groups → /ecs/graphrag-hackathon
   ```

---

## Troubleshooting

- **Deployment fails**: Check CloudWatch logs in `/ecs/graphrag-hackathon`
- **Container won't start**: Verify all environment variables are set correctly
- **Permission errors**: Ensure IAM roles have correct policies attached
- **Port 8080 not accessible**: Check security group inbound rules

---

## Testing After Deployment

Once deployed, test your API:

```bash
# Get your ECS service public IP (if using public subnet)
TASK_ARN=$(aws ecs list-tasks --cluster graphrag-hackathon-cluster --service-name graphrag-hackathon-service --query 'taskArns[0]' --output text)
ENI_ID=$(aws ecs describe-tasks --cluster graphrag-hackathon-cluster --tasks $TASK_ARN --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --query 'NetworkInterfaces[0].Association.PublicIp' --output text)

# Test the API
curl http://$PUBLIC_IP:8080/
curl -X POST http://$PUBLIC_IP:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many patients are in the database?"}'
```

