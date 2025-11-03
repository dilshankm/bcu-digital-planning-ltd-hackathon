# Quick Setup Guide - Add These 13 Secrets

## Step 1: Go to GitHub
**Your Repo → Settings → Secrets and variables → Actions → New repository secret**

---

## Step 2: Add Each Secret (13 total)

### AWS (3)
1. `AWS_ACCESS_KEY_ID` = Your AWS access key
2. `AWS_SECRET_ACCESS_KEY` = Your AWS secret key
3. `AWS_REGION` = `us-east-1` (or your region)

### Docker Hub (2)
4. `DOCKER_USERNAME` = `dilshankm`
5. `DOCKER_PASSWORD` = Your Docker Hub token

### ECS (4)
6. `ECS_CLUSTER_NAME` = `graphrag-hackathon-cluster`
7. `ECS_SERVICE_NAME` = `graphrag-hackathon-service`
8. `ECS_EXECUTION_ROLE_ARN` = `arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole`
9. `ECS_TASK_ROLE_ARN` = `arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskRole`

### App Config (4)
10. `OPENAI_API_KEY` = `sk-proj-...`
11. `NEO4J_URI` = `neo4j+s://xxxxx.databases.neo4j.io`
12. `NEO4J_USERNAME` = `neo4j`
13. `NEO4J_PASSWORD` = Your Neo4j password

---

## Step 3: Create AWS Infrastructure (one-time)

```bash
# Create IAM roles
aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam create-role --role-name ecsTaskRole --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

# Create ECS cluster
aws ecs create-cluster --cluster-name graphrag-hackathon-cluster

# Create log group
aws logs create-log-group --log-group-name /ecs/graphrag-hackathon

# Setup networking
VPC_ID=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[0:2].SubnetId' --output text | tr '\t' ',')
SG_ID=$(aws ec2 create-security-group --group-name graphrag-sg --description "GraphRAG security group" --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8080 --cidr 0.0.0.0/0

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

## Step 4: Tell Me When Done!

Once you've:
- ✅ Added all 13 secrets to GitHub
- ✅ Created AWS infrastructure

**Tell me to push and it will auto-deploy!** 🚀

