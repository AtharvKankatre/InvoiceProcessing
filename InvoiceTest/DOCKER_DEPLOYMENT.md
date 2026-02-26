# Cooper SAP Invoice - Docker Deployment Guide (Windows Server)

## Prerequisites for Windows Server

### 1. Install Docker Desktop for Windows

1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
2. Run the installer
3. **Important:** During installation, ensure "Use WSL 2 instead of Hyper-V" is selected (recommended)
4. Restart the computer after installation

### 2. Configure Docker Desktop to Start on Boot

**This is CRITICAL for auto-restart after system reboot:**

1. Open Docker Desktop
2. Click the ⚙️ **Settings** icon (top right)
3. Go to **General** tab
4. ✅ Enable **"Start Docker Desktop when you sign in to Windows"**
5. ✅ Enable **"Open Docker Dashboard at startup"** (optional)
6. Click **Apply & Restart**

### 3. Configure Windows Auto-Login (Optional but Recommended)

For truly unattended auto-restart, configure Windows to auto-login:

1. Press `Win + R`, type `netplwiz`, press Enter
2. Uncheck **"Users must enter a user name and password to use this computer"**
3. Click OK and enter the password twice
4. Restart to verify auto-login works

---

## Deployment Steps

### Step 1: Copy Project Files to Server

Copy the entire `InvoiceTest` folder to the server. Recommended location:
```
C:\Cooper\InvoiceTest\
```

The folder should contain:
```
InvoiceTest/
├── docker-compose.yml
├── DOCKER_DEPLOYMENT.md
├── sap-invoice-backend-main/
│   ├── Dockerfile
│   ├── .env
│   └── ... (Django project files)
└── cooper_frontend-main/
    ├── Dockerfile
    ├── nginx.conf
    └── ... (React project files)
```

### Step 2: Verify Backend .env File

Open `sap-invoice-backend-main\.env` and verify database settings:

```env
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost      # or IP of PostgreSQL server
DB_PORT=5432
SECRET_KEY=your_secret_key
ALLOWED_HOSTS=*
```

### Step 3: Build and Start Containers

Open **PowerShell as Administrator** and run:

```powershell
# Navigate to project folder
cd C:\Cooper\InvoiceTest

# Build containers (first time only, or after code changes)
docker-compose build

# Start containers in background
docker-compose up -d
```

### Step 4: Verify Containers are Running

```powershell
docker-compose ps
```

You should see:
```
NAME              STATUS                   PORTS
cooper-backend    Up (healthy)             0.0.0.0:8000->8000/tcp
cooper-frontend   Up (healthy)             0.0.0.0:80->80/tcp
```

### Step 5: Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost or http://[server-ip] |
| Backend API | http://localhost:8000 |

---

## Auto-Restart Verification

### Test 1: Container Crash Recovery

```powershell
# Manually stop backend container
docker stop cooper-backend

# Wait 10 seconds, then check - it should restart automatically
docker ps
```

### Test 2: System Reboot Recovery

1. Restart the Windows server
2. Wait for Windows to boot and Docker Desktop to start (1-2 minutes)
3. Open PowerShell and run:
   ```powershell
   docker ps
   ```
4. Both containers should be running automatically

---

## Common Windows Commands

### View Logs
```powershell
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### Stop All Services
```powershell
docker-compose down
```

### Restart Services
```powershell
docker-compose restart
```

### Rebuild After Code Changes
```powershell
docker-compose build --no-cache
docker-compose up -d
```

### Check Container Health
```powershell
docker inspect --format='{{.State.Health.Status}}' cooper-backend
docker inspect --format='{{.State.Health.Status}}' cooper-frontend
```

---

## Troubleshooting Windows-Specific Issues

### Issue: Docker Desktop won't start

**Solution:**
1. Ensure Hyper-V or WSL2 is enabled
2. Run in PowerShell (Admin):
   ```powershell
   wsl --update
   wsl --set-default-version 2
   ```
3. Restart and try again

### Issue: Port 80 already in use

**Solution:**
1. Check what's using port 80:
   ```powershell
   netstat -ano | findstr :80
   ```
2. Stop IIS if running:
   ```powershell
   iisreset /stop
   ```
3. Or change port in `docker-compose.yml`:
   ```yaml
   ports:
     - "8080:80"  # Use 8080 instead
   ```

### Issue: Database connection failed

**Solution:**
1. Verify PostgreSQL is running
2. Check if PostgreSQL allows connections from Docker:
   - Edit `pg_hba.conf` to allow `host all all 172.0.0.0/8 md5`
3. Use host IP instead of `localhost` in `.env`:
   ```env
   DB_HOST=192.168.1.100  # actual server IP
   ```

### Issue: Containers don't restart after reboot

**Solution:**
1. Verify Docker Desktop is set to start on boot
2. Check Windows Event Viewer for Docker errors
3. Ensure the Windows user is logged in (or auto-login is configured)

---

## Firewall Configuration

If accessing from other machines, open ports in Windows Firewall:

```powershell
# Allow HTTP traffic
New-NetFirewallRule -DisplayName "Cooper Frontend" -Direction Inbound -Port 80 -Protocol TCP -Action Allow

# Allow API traffic
New-NetFirewallRule -DisplayName "Cooper Backend" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
```

---

## Summary: Auto-Restart Guarantee

| Scenario | What Happens |
|----------|--------------|
| Container crashes | ✅ Docker restarts it automatically |
| Docker Desktop restarts | ✅ Containers restart automatically |
| Windows reboots | ✅ Docker Desktop starts, then containers start |
| Power failure + restart | ✅ Same as Windows reboot |

**Requirements for auto-restart:**
1. ✅ `restart: always` in docker-compose.yml (already configured)
2. ✅ Docker Desktop set to start on Windows boot
3. ✅ Windows auto-login configured (for unattended scenarios)
