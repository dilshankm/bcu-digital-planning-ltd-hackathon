# AWS Learner Lab Credential Management Guide

## 🔄 **Why Credentials Expire**

AWS Learner Lab provides **temporary credentials** that expire every 3-4 hours. This is a security feature of the sandbox environment.

---

## 🚀 **Two Deployment Workflows**

### 1. **Automatic Deployment** (deploy.yml)
- Triggers on every push to `main` or `master`
- **Use for**: Active development
- **Problem**: Fails when credentials expire

### 2. **Manual Deployment** (deploy-manual.yml) ⭐ **RECOMMENDED FOR HACKATHON**
- Triggers only when you manually click "Run workflow"
- **Use for**: When credentials have been refreshed
- **Benefit**: Deploy exactly when you want

---

## 📝 **How to Refresh Credentials & Deploy**

### Step 1: Get Fresh Credentials (Every 3-4 hours)

1. Go to **AWS Learner Lab**: https://awsacademy.instructure.com/
2. Start the lab (green "Start Lab" button)
3. Click **"AWS Details"**
4. Click **"Show"** next to "AWS CLI credentials"
5. Copy all three values:
   ```
   aws_access_key_id=ASIA...
   aws_secret_access_key=...
   aws_session_token=...
   ```

### Step 2: Update GitHub Secrets

1. Go to your repo: https://github.com/dilshankm/bcu-digital-planning-ltd-hackathon
2. Go to **Settings → Secrets and variables → Actions**
3. Update these **3 secrets** (click each one and update):
   - `AWS_ACCESS_KEY_ID` → paste new access key
   - `AWS_SECRET_ACCESS_KEY` → paste new secret key
   - `AWS_SESSION_TOKEN` → paste new session token

### Step 3: Trigger Manual Deployment

1. Go to **Actions** tab in your repo
2. Click **"Manual Deploy to AWS Fargate"** (left sidebar)
3. Click **"Run workflow"** (right side)
4. (Optional) Add a reason: "Refreshed credentials"
5. Click green **"Run workflow"** button
6. Watch it deploy! ✅

---

## ⏰ **Credential Expiration Timeline**

```
Hour 0:  🟢 Get credentials → Update secrets → Deploy
Hour 1:  🟢 Credentials valid
Hour 2:  🟢 Credentials valid  
Hour 3:  🟡 Credentials expiring soon
Hour 4:  🔴 Credentials expired → Need refresh
```

**💡 Pro Tip**: Set a timer for 3 hours to refresh credentials before they expire!

---

## 🎯 **Best Practices for Hackathon**

### Option A: Active Development
1. Keep AWS Learner Lab running
2. Refresh credentials every 3 hours
3. Use **Manual Deployment** workflow
4. Update secrets → Run workflow → Deploy

### Option B: Demo Time
1. Refresh credentials just before demo
2. Deploy once using manual workflow
3. Your ECS service stays running even after credentials expire
4. **Important**: Can't redeploy without fresh credentials

### Option C: Final Submission
1. Keep automatic deployment (deploy.yml) for final push
2. Refresh credentials
3. Make final changes
4. Push to main → Auto-deploy

---

## 🐳 **Alternative: Local Docker Deploy**

If credentials keep expiring, deploy locally:

```bash
# Build locally
docker build -t dilshankm/graphrag-hackathon:latest .

# Push to Docker Hub
docker push dilshankm/graphrag-hackathon:latest

# Update ECS (with fresh credentials in terminal)
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

aws ecs update-service \
  --cluster graphrag-hackathon-cluster \
  --service graphrag-hackathon-service \
  --force-new-deployment \
  --region eu-central-1
```

---

## ❓ **Troubleshooting**

### Error: "Security token expired"
✅ **Fix**: Refresh credentials (Steps 1-2 above), then run manual workflow

### Error: "Invalid security token"
✅ **Fix**: Make sure you copied ALL THREE credentials correctly (access key, secret, **and session token**)

### Question: "Do I need to update secrets for every deployment?"
❌ **No!** Only when credentials expire (every 3-4 hours)

### Question: "Will my service stop when credentials expire?"
❌ **No!** The ECS service keeps running. You just can't **deploy new versions** until you refresh.

---

## 🎬 **Quick Reference**

**When to use Manual Workflow:**
- ✅ After refreshing credentials
- ✅ For controlled demo deploys
- ✅ When automatic deploy fails

**When automatic deploy fails:**
1. Refresh credentials in AWS Learner Lab
2. Update 3 GitHub secrets
3. Use Manual Workflow to deploy

---

## 📞 **Need Help?**

- **Credentials expired?** → Follow Steps 1-3 above
- **Deployment failing?** → Check GitHub Actions logs
- **Service not starting?** → Check CloudWatch logs at `/ecs/graphrag-hackathon`

