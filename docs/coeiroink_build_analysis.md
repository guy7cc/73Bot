# COEIROINK (v0.14.5 / c-1.7.3) Docker Build Error Analysis

This document summarizes the investigation into why the Docker build for the `shirowanisan/voicevox_engine` repository (branch: `c-1.7.3+v-0.14.5`) failed when attempting to build it as part of the 73Bot project using Docker Compose.

## 1. Initial Failure: Missing `speaker_info`
When executing the build natively via Docker Compose (using the `build: https://github.com/...` directive), the build process failed at the following step in the original repository's `Dockerfile`:

```dockerfile
ADD ./speaker_info /opt/voicevox_engine/speaker_info
```

**Cause:**
The `speaker_info` directory does not exist in the remote Git repository. In the official VOICEVOX build workflow, this directory is generated dynamically by a script (`build_util/process_voicevox_resource.bash`) that pulls external resources *before* the Docker build context is sent to the daemon. Because Docker Compose's direct URL build feature simply clones the raw repository and immediately runs the `Dockerfile`, this prerequisite generation step was missing, causing the `ADD` command to fail.

## 2. Second Attempt: Wrapper Dockerfile and Dependency Issues
To bypass the missing `speaker_info` problem without requiring the user to run manual generation scripts on their host machine, a wrapper `Dockerfile` (`coeiroink-v2/Dockerfile`) was constructed. 

This wrapper:
1. Used the official, pre-built `voicevox/voicevox_engine:cpu-ubuntu20.04-latest` image as a base (which already has Python configured and the core ONNX runtime installed).
2. Cloned the target `c-1.7.3+v-0.14.5` branch.
3. Overwrote the engine files inside the container with the cloned branch's code.
4. Attempted to install the specific Python dependencies listed in the branch's `requirements.txt`.

### The Python 3.11 Compatibility Problem
During the `pip install -r requirements.txt` step in the wrapper Dockerfile, the build failed with severe C++ compilation errors (`exit code: 1` from `gcc`).

**Failure Logs Extract:**
```text
error: Command "gcc -pthread -Wsign-compare -DNDEBUG -g -fwrapv -O3 [...]  failed with exit status 1
ERROR: Failed building wheel for numpy
ERROR: Could not build wheels for numpy, which is required to install pyproject.toml-based projects
```

**Cause:**
1. **Base Image Python Version:** The `voicevox/voicevox_engine:cpu-ubuntu20.04-latest` image currently uses **Python 3.11**.
2. **Pinned Legacy Dependencies:** The `c-1.7.3+v-0.14.5` branch has its dependencies strictly pinned to older versions (e.g., `numpy==1.20.0`, `scipy==1.7.1`).
3. **Missing Pre-compiled Wheels:** These older versions of `numpy` and `scipy` do not have pre-compiled binary wheels available for Python 3.11 on PyPI. 
4. **Source Compilation Failure:** Because wheels are missing, `pip` attempts to compile `numpy` from C++ source. However, the legacy `numpy 1.20.0` source code uses outdated C-API structures that are fundamentally incompatible with Python 3.11, causing `gcc` to throw fatal errors.

### The `pyopenjtalk` Bottleneck
As an experiment to force the build, the `numpy` and `scipy` version pins were relaxed (`numpy>=1.20.0`) in the `requirements.txt` to allow `pip` to fetch modern, Python 3.11-compatible versions. 

However, the build immediately failed on the next dependency: `pyopenjtalk`.
The branch requires a specific commit of `pyopenjtalk` pulled directly from GitHub (`git+https://github.com/VOICEVOX/pyopenjtalk@f4ade29...`). This specific older snapshot of `pyopenjtalk` also requires C++ compilation and similarly failed against the Python 3.11 headers.

## 3. Conclusion

The `c-1.7.3+v-0.14.5` branch of this COEIROINK fork is highly tightly-coupled to an older Python runtime environment (likely Python 3.8, as hinted by `ARG PYTHON_VERSION=3.8.10` in its own Dockerfile). 

**Why it's difficult to automate via Compose:**
To successfully build this specific branch from scratch via `docker compose up`, the Compose file would need to:
1. Re-implement the complex multi-stage Python 3.8 compilation process defined in the original `Dockerfile`.
2. Simultaneously execute the bash scripts required to download and generate the `speaker_info` resources before the Docker build context is evaluated—something Docker Compose cannot do natively without external helper scripts on the host machine.

**Recommendation:**
Attempting to force this specific branch to build automatically via a simple `docker-compose.yml` is unfeasible without significant architectural hacks. Falling back to a different, potentially more modernized branch (or one that provides its own pre-built Docker image) is the correct and most stable path forward.
