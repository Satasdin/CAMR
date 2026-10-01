# CAMR for Android (parked prototype)

A Kotlin/Jetpack Compose port of the CAMR engine for phones. It includes on-device memory in SQLite, gating,
entity bridging, chat as memory and learning from 👍. Generation runs on-device with MediaPipe/LiteRT
model files, or through Ollama on the user's own computer over Wi-Fi.

**Status:** it compiles and its JVM unit tests pass (`./gradlew testReleaseUnitTest assembleRelease`, APK about 57 MB,
arm64). It has **not** been run on a device or emulator. Development is paused while the desktop app is the focus.
The gating threshold for its on-device embedder (Universal Sentence Encoder) has not been calibrated yet.
