# Immich Bulk Import Guide

This directory contains the configuration for Immich. A dedicated volume `pv-nas-import` has been configured to import existing photos from the NAS (`/tank_data/import/photo_nas`).

## How to Import Photos

To import photos from the mapped import volume, follow these steps:

1.  **Generate an API Key**:
    *   Log in to Immich.
    *   Go to **User Settings** (top right) -> **API Keys**.
    *   Create a new key.
    *   **Important**: Select **"All Permissions"** (or Full Access). Restricting permissions can cause the import CLI to fail silently (duplicate check issues).
    *   Copy the key.

2.  **Run the Import Command**:
    Open a terminal and run the following command. Replace `<YOUR_KEY>` with your actual API Key.

    ```bash
    kubectl exec -it -n media deploy/immich-server -- \
      npx @immich/cli \
      --url http://localhost:2283 \
      --key <YOUR_KEY> \
      upload \
      --recursive \
      //mnt/import
    ```

    > **Note for Windows Users (Git Bash)**: The double slash `//mnt/import` is required to prevent Git Bash from converting the path to a local Windows path.

### Options to consider
*   `--dry-run`: Use this flag first to simulate the import without moving files.
*   `--delete`: Deletes the source files after successful upload (use with caution).

## Long-Running Imports (Recommended)

For large imports, it is highly recommended to use `screen` so the process doesn't stop if your terminal disconnects.

1.  **Enter the container**:
    ```bash
    kubectl exec -it -n media deploy/immich-server -- bash
    ```

2.  **Install screen** (if missing):
    ```bash
    apt-get update && apt-get install -y screen
    ```

3.  **Start a screen session**:
    ```bash
    screen
    ```

4.  **Run the import** (inside the container):
    ```bash
    npx @immich/cli --url http://localhost:2283 --key <YOUR_KEY> upload --recursive /mnt/import
    ```
    *(Note: Inside the container, you don't need the double slash `//`)*

5.  **Detach**: Press `Ctrl+A` then `D`.
    You can now close your terminal. To resume later: `screen -r`.

