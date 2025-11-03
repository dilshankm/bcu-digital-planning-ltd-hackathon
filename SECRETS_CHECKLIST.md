# GitHub Secrets Checklist - COMPLETE LIST

## 📋 All 13 Required Secrets

Go to: **GitHub Repository → Settings → Secrets and variables → Actions → New repository secret**

---

## ✅ Copy this template and fill in your values:

```bash
# ===== AWS Credentials (3) =====
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# ===== Docker Hub (2) =====
DOCKER_USERNAME=dilshankm
DOCKER_PASSWORD=

# ===== ECS Configuration (4) =====
ECS_CLUSTER_NAME=graphrag-hackathon-cluster
ECS_SERVICE_NAME=graphrag-hackathon-service
ECS_EXECUTION_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole
ECS_TASK_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskRole

# ===== Application Environment Variables (4) =====
OPENAI_API_KEY=sk-proj-...
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=
```

---

## 📝 Detailed Breakdown:

### 1. AWS Credentials (3 secrets)
- [ ] **AWS_ACCESS_KEY_ID** - Your AWS IAM access key
- [ ] **AWS_SECRET_ACCESS_KEY** - Your AWS IAM secret key
- [ ] **AWS_REGION** - AWS region (e.g., `us-east-1`, `eu-west-1`)

### 2. Docker Hub (2 secrets)
- [ ] **DOCKER_USERNAME** - Your Docker Hub username (e.g., `dilshankm`)
- [ ] **DOCKER_PASSWORD** - Docker Hub access token (create at hub.docker.com → Security)

### 3. ECS Configuration (4 secrets)
- [ ] **ECS_CLUSTER_NAME** - ECS cluster name (e.g., `graphrag-hackathon-cluster`)
- [ ] **ECS_SERVICE_NAME** - ECS service name (e.g., `graphrag-hackathon-service`)
- [ ] **ECS_EXECUTION_ROLE_ARN** - IAM role ARN for ECS task execution
- [ ] **ECS_TASK_ROLE_ARN** - IAM role ARN for ECS task (can be same as execution role)

### 4. Application Secrets (4 secrets)
- [ ] **OPENAI_API_KEY** - Your OpenAI API key (from platform.openai.com)
- [ ] **NEO4J_URI** - Neo4j database connection URI
- [ ] **NEO4J_USERNAME** - Neo4j username (usually `neo4j`)
- [ ] **NEO4J_PASSWORD** - Neo4j password

---

## 🔧 Quick Setup for IAM Roles

### Create ECS Execution Role:
```bash
# Create trust policy
cat > ecs-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create execution role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document file://ecs-trust-policy.json

# Attach policy
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Get ARN (use this for ECS_EXECUTION_ROLE_ARN)
aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.Arn' --output text
```

### Create ECS Task Role:
```bash
# Create task role (same trust policy)
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document file://ecs-trust-policy.json

# Get ARN (use this for ECS_TASK_ROLE_ARN)
aws iam get-role --role-name ecsTaskRole --query 'Role.Arn' --output text
```

---

## 🚀 Before First Deployment

### 1. Create ECS Infrastructure:
```bash
# Create cluster
aws ecs create-cluster --cluster-name graphrag-hackathon-cluster

# Create CloudWatch log group
aws logs create-log-group --log-group-name /ecs/graphrag-hackathon

# Get VPC and subnet info
VPC_ID=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0:2].SubnetId' \
  --output text | tr '\t' ',')

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name graphrag-sg \
  --description "Security group for GraphRAG" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Allow port 8080
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0

# Create ECS service
aws ecs create-service \
  --cluster graphrag-hackathon-cluster \
  --service-name graphrag-hackathon-service \
  --task-definition graphrag-hackathon-task:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"
```

---

## ✅ Checklist Before Pushing

- [ ] All 13 secrets added to GitHub
- [ ] ECS cluster created
- [ ] ECS service created
- [ ] CloudWatch log group created
- [ ] IAM roles created
- [ ] Security group configured

**Once done, tell me and I'll push to GitHub!** 🚀
