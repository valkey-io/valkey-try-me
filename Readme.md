# Try-Valkey Images

This repository provides tools and instructions for creating and running custom images for the Try Valkey project. The emulator operates on a 32-bit Alpine Linux base, ensuring a lightweight and efficient environment. The images include the Valkey server and CLI, prepared for booting with all necessary configurations.
This project is based on the [v86 project](https://github.com/copy/v86). Users seeking additional customization options or expanded emulator support should refer to the v86 repository.

---

## Repository Structure

### Image Creation Tools
- **src:** Contains files required to build a filesystem that includes Valkey, fully configured and ready to run.
- **utils:** Provides debugging tools and utilities to modify the image, save states, and make additional customizations.
- **example:** A working example demonstrating how to use the saved states. 
### Binary Image Storage
- Prebuilt filesystems and state binaries are hosted on a CDN. The relevant URLs are listed in `versions.json`.

---

## Run Automated Build

#### Prerequisites

**1. Ensure Docker is Installed**
Verify that Docker is installed and running by executing:

```bash
docker --version
```

If Docker is not installed, refer to the installation guides for your operating system:
- [Docker Desktop installation guide](https://docs.docker.com/desktop/) (macOS and Windows)
- [Docker Engine installation guide](https://docs.docker.com/engine/install/) (Linux and other OS)

**2. Python3 with Playwright**

```bash
# Activate venv first
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# install browser binary!
playwright install chromium
```

To generate a default state for a desired valkey version, run the following command:
```bash
MODE=local AUTO_SAVE_STATE=true VALKEY_VERSION=<version tag> \
VALKEY_DOWNLOAD_URL=<download_url> \
VALKEY_DOWNLOAD_SHA=<download_sha> \
./src/build.sh
```

For example:
```bash
MODE=local AUTO_SAVE_STATE=true VALKEY_VERSION=8.1.0 \
VALKEY_DOWNLOAD_URL=https://github.com/valkey-io/valkey/archive/refs/tags/8.1.0.tar.gz \
VALKEY_DOWNLOAD_SHA=559274e81049326251fa5b1e1c64d46d3d4d605a691481e0819133ca1f1db44f \
./src/build.sh
```

**This automation will:**
1. Build a docker image with valkey
2. Generate a file system for the v86 emulator
3. Launch the emulated file system and wait for the boot to complete
4. Download and compress the image state

The downloaded state will have the valkey-server and valkey-cli loaded and ready to go.
The files generated in this automation will be saved in a new `<version-tag>` directory.  
*Note:* The automated process take approximately 5 minutes to complete. 



## Manual Build Process

You can either build the filesystem from scratch (`MODE="local"`) or use a prebuilt one (`MODE="remote"`).

### Step 1: Creating a Filesystem 

### Option 1: Use a Prebuilt Filesystem (`MODE="remote"`)

If a filesystem for your desired version already exists in `versions.json`, run: 

   ```bash
   MODE=remote VALKEY_VERSION=<version-tag> ./src/build.sh
   ```
A directory named `<version-tag>/` will be created.
`image_creator.html` will be generated and automatically configured to use remote CDN URLs from `versions.json`.


### Option 2: Build Filesystem from Scratch (`MODE="local"`)

#### Prerequisites

**Ensure Docker is Installed**
Verify that Docker is installed and running by executing:

```bash
docker --version
```

If Docker is not installed, refer to the installation guides for your operating system:
- [Docker Desktop installation guide](https://docs.docker.com/desktop/) (macOS and Windows)
- [Docker Engine installation guide](https://docs.docker.com/engine/install/) (Linux and other OS)

####  Build
   Run:
   ```bash
   MODE=local VALKEY_VERSION=<version-tag> \
   VALKEY_DOWNLOAD_URL=<download_url> \
   VALKEY_DOWNLOAD_SHA=<download_sha> \
   ./src/build.sh
   ```
   - For `VALKEY_VERSION`, `VALKEY_DOWNLOAD_URL` and `VALKEY_DOWNLOAD_SHA`, refer to the [Valkey hashes file](https://github.com/valkey-io/valkey-hashes).

   for example:
   ```bash
   MODE=local VALKEY_VERSION=8.1.0 \
   VALKEY_DOWNLOAD_URL=https://github.com/valkey-io/valkey/archive/refs/tags/8.1.0.tar.gz \
   VALKEY_DOWNLOAD_SHA=559274e81049326251fa5b1e1c64d46d3d4d605a691481e0819133ca1f1db44f \
   ./src/build.sh
   ```
   A directory named `<version-tag>/` will be created with the generated filesystem and state directories.
   `image_creator.html` will be generated and preconfigured to use the local paths for the generated filesystem.

## Step 2: Customize Image and Save State

1. Run a local server:
   
      ```bash
      python3 -m http.server 8888
      ```
2. In web browser, navigate to http://localhost:8888/<version-tag>/image_creator.html.
   Wait for the boot process to complete. You'll know it's finished when data appears in the server log.
3. Modify the image as needed (e.g., loading keys, editing state via CLI or VM terminal).
4. Click **"Download State"** to download a binary file of the current state.
5. Compress the binary state file that was downloaded in the previous step.  
   
   ```bash
    gzip <binary_state_file>
   ```
   This ensures compatibility with the Try-Valkey page.
6. After compressing, move the compressed state file to the `<version-tag>/state` directory. 
   ```bash
    mv <binary_state_file>.gz <version-tag>/state/
   ```

## Test Your State
Use the examples in `/example` to verify that your saved state works correctly:
- Update the filesystem and state paths to point to your created versions.
- Launch and confirm expected behavior in the emulator.


## Environment Variables Reference
| Variable | Description | 
|----------|-------------|
| `MODE` | Build mode: `local` (build from scratch) or `remote` (prebuilt) | 
| `AUTO_SAVE_STATE` | Automatically save state after build: `true` or `false` | 
| `VALKEY_VERSION` | Valkey version tag |
| `VALKEY_DOWNLOAD_URL` | Download URL for Valkey source | 
| `VALKEY_DOWNLOAD_SHA` | SHA256 hash for verification | 
