# CodeIQ GitHub Integration Setup Guide

This guide walks you through setting up GitHub OAuth and the CodeIQ GitHub App for the CodeIQ documentation generation pipeline.

## Overview

The GitHub integration has two components:

1. **GitHub OAuth** - Allows users to authenticate with GitHub and grant CodeIQ access to their repositories and profile information.
2. **CodeIQ GitHub App** - An organizational application that can clone private repositories, create branches, commit changes, and open pull requests on behalf of users.

## Prerequisites

- A GitHub account (or GitHub organization for production use)
- Access to create GitHub Apps and register OAuth applications
- CodeIQ backend and frontend running (or deployed)
- Access to environment variable configuration

## Part 1: GitHub OAuth Setup

### Step 1: Register OAuth Application

1. Go to GitHub Developer Settings: https://github.com/settings/developers
2. Click **OAuth Apps** in the left sidebar
3. Click **New OAuth App**
4. Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Application name** | CodeIQ |
   | **Homepage URL** | `http://localhost:3000` (development) or your production domain |
   | **Authorization callback URL** | `http://localhost:3000/dashboard` (development) or `https://yourdomain.com/dashboard` |

5. Click **Register application**
6. You'll see the **Client ID** and **Client Secret**

### Step 2: Configure Environment Variables

Add these to your `.env.local` (frontend) and `.env` (backend):

**Frontend (.env.local):**
```env
NEXT_PUBLIC_GITHUB_CLIENT_ID=your_client_id_here
```


**Backend (.env):**
```env
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
```

> ⚠️ **Important**: Never commit `GITHUB_CLIENT_SECRET` to version control!

## Part 2: CodeIQ GitHub App Setup

### Step 1: Create GitHub App

1. Go to GitHub App Settings: https://github.com/settings/apps
2. Click **New GitHub App**
3. Fill in the configuration:

   **General Information:**
   - **GitHub App name**: CodeIQ
   - **Homepage URL**: `http://localhost:3000` or your production domain
   - **Webhook active**: ✓ (Checked)
   - **Webhook URL**: `http://localhost:8000/api/github/webhook/installation` (development) or your production domain
   - **Webhook secret**: Generate a secure random string (e.g., using `openssl rand -hex 32`)

   **OAuth:**
   - **Client ID**: (Auto-generated, note this)
   - **Client Secret**: Generate a new client secret and note it
   - **Scopes**: 
     - `user` - Read user profile
     - `repo` - Access repositories
   - **Authorization callback URL**: Not needed for this app (only used with OAuth)

   **Permissions:**
   - **Repository permissions:**
     - `Contents (read & write)` - To commit documentation
     - `Pull requests (read & write)` - To create PRs
   - **Account permissions:**
     - `Profile (read)` - To read user info

   **Where can this GitHub App be installed?:**
   - `Any account` (or just your account for testing)

4. Scroll down and click **Create GitHub App**

### Step 2: Generate Private Key

1. On the GitHub App settings page, scroll down to **Private keys**
2. Click **Generate a private key**
3. A `.pem` file will download automatically
4. Save this file securely - you'll need it for the backend

### Step 3: Configure Backend Environment

Add these to your `.env`:

```env
GITHUB_APP_ID=your_app_id_here
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret_here
```

> **Important Notes:**
> - Replace newlines in the private key with `\n`
> - To properly format the private key for env vars:
>   ```bash
>   # On Linux/Mac
>   cat your-app-name.pem | jq -Rs '.'
>   
>   # Or manually: copy the private key and replace line breaks with \n
>   ```

### Step 4: Install GitHub App

1. Go to your GitHub App settings page
2. Look for **Install App** or go to: `https://github.com/apps/codeiq/installations/new`
3. Select your account (or organization)
4. Choose which repositories to give access to:
   - Select **Only select repositories** (recommended)
   - Choose the repositories you want CodeIQ to work with
5. Click **Install**

### Step 5: Verify Installation

After installation, you should be able to:
- See CodeIQ in your repository settings under **Installed GitHub Apps**
- The app should appear in your account's installed apps

## Part 3: Frontend Configuration

### Environment Variables (Frontend .env.local)

```env
# GitHub OAuth
NEXT_PUBLIC_GITHUB_CLIENT_ID=your_client_id_here

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Part 4: Backend Configuration

### Environment Variables (Backend .env)

```env
# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here

# GitHub App
GITHUB_APP_ID=your_app_id_here
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_APP_WEBHOOK_SECRET=your_webhook_secret_here

# CORS (allow your frontend)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## Part 5: Database Schema

The GitHub integration stores user credentials and app installations. Ensure your MongoDB has:

**Users Collection:**
```javascript
{
  "_id": ObjectId,
  "email": String,
  "github_id": Number,                    // GitHub user ID
  "github_login": String,                 // GitHub username
  "github_avatar_url": String,            // Avatar URL
  "github_access_token": String,          // OAuth token (encrypted in production)
  "github_token_expires_at": String,      // ISO date
  "github_connected_at": String,          // ISO date when connected
  "github_app": {                         // Map of repo IDs to installation info
    "[repo_id]": {
      "name": String,
      "full_name": String,
      "installation_id": Number,
      "installed_at": String
    }
  }
}
```

**Repositories Collection (additions):**
```javascript
{
  "_id": ObjectId,
  "github_repo_id": Number,               // GitHub repository ID
  "github_repo_full_name": String,        // owner/repo
  "github_pr_number": Number,             // PR number (after creation)
  "github_pr_url": String,                // PR URL
  "github_pr_created_at": String          // ISO date
}
```

## Testing the Integration

### 1. Test OAuth Flow

1. Navigate to the dashboard
2. Look for "Connect GitHub" button
3. Click it
4. You should be redirected to GitHub
5. Authorize the application
6. You should be redirected back to the dashboard
7. Verify your GitHub profile appears in the UI

### 2. Test Repository Selection

1. After connecting (or on the "New Project" dialog)
2. Click "GitHub Connected" tab
3. You should see your GitHub repositories listed
4. For repos without the CodeIQ app: see "Install App" button
5. For repos with the app: see "Clone" button

### 3. Test App Installation

1. Click "Install App" for a repository
2. You'll be redirected to GitHub to install the app
3. Select the repository and click "Install"
4. You should be redirected back to CodeIQ
5. The app status should change to "App Installed"

### 4. Test Clone and Analysis

1. Click "Clone" for a repository with the app installed
2. The repository will be cloned
3. You'll be redirected to the pipeline page
4. The analysis should start automatically

### 5. Test PR Creation

1. After analysis completes
2. On the pipeline results page, look for "Create Pull Request" button
3. It should only be enabled if:
   - Documentation was generated
   - The GitHub App is installed
4. Click the button
5. Fill in the PR details
6. Click "Create PR"
7. A PR should be created on the GitHub repository
8. You'll see the PR URL

## Troubleshooting

### Issue: "GitHub not configured"
- **Solution**: Make sure `GITHUB_CLIENT_ID` is set in frontend `.env.local`

### Issue: OAuth fails with "Invalid client_id"
- **Solution**: Check that the client ID in `.env` matches the one in GitHub Developer Settings

### Issue: Can't fetch repositories
- **Solution**: 
  - Verify GitHub OAuth token is saved correctly
  - Check that token has `user` and `repo` scopes
  - Ensure MongoDB is connected

### Issue: App installation fails
- **Solution**:
  - Verify `GITHUB_APP_ID` is set correctly
  - Check that the private key is properly formatted (newlines as `\n`)
  - Ensure webhook URL is accessible from GitHub

### Issue: PR creation fails
- **Solution**:
  - Verify app has read & write access to `Contents` and `Pull Requests`
  - Check that the repository is installed
  - Ensure `main` or `master` branch exists (or update the PR creation code)

### Issue: Webhook not received
- **Solution**:
  - Check that webhook URL in GitHub App settings is correct
  - Verify the URL is publicly accessible
  - Check backend logs for webhook handling
  - Verify webhook secret matches `GITHUB_APP_WEBHOOK_SECRET`

## Security Best Practices

1. **Environment Variables**: Never commit secrets to version control
2. **Token Storage**: In production, encrypt stored GitHub tokens in the database
3. **Token Rotation**: Implement token refresh for long-lived applications
4. **Scope Limitation**: Only request necessary GitHub API scopes
5. **Webhook Validation**: Always validate webhook signatures
6. **CORS**: Restrict CORS origins to your domain in production

## API Endpoints

### GitHub OAuth

**POST /api/github/authorize**
- Exchanges OAuth code for access token
- Stores token in user's database record
- Returns user's GitHub profile

**GET /api/github/repositories**
- Fetches user's own repositories
- Returns list with installation status for each
- Requires GitHub OAuth connection

### GitHub App

**POST /api/github/app/install-url**
- Returns URL to install CodeIQ GitHub App
- User is redirected to complete installation

**POST /api/github/webhook/installation**
- Receives webhook events from GitHub
- Processes app installation/uninstallation
- Updates database with installation info

**POST /api/github/pr/create**
- Creates a pull request with generated documentation
- Requires app to be installed on the repository
- Uses app credentials to create PR

## References

- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps/creating-an-oauth-app)
- [GitHub App Documentation](https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app)
- [GitHub API Implementation Guide](https://docs.github.com/en/rest?apiVersion=2022-11-28)
