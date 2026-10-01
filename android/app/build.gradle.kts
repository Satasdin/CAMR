import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "io.github.satasdin.camr"
    compileSdk = 36
    defaultConfig {
        applicationId = "io.github.satasdin.camr"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "0.2.0"
        // Phones are 64-bit ARM; MediaPipe's native libraries make every extra ABI ~40 MB.
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key so testers can sideload the APK; use a real key for a store release.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    androidResources { noCompress += "tflite" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

// The on-device text embedder (Universal Sentence Encoder, 6 MB, Apache-2.0) is fetched at build time
// rather than committed to git.
val embedderAsset = layout.projectDirectory.file("src/main/assets/universal_sentence_encoder.tflite")
val downloadEmbedder by tasks.registering {
    outputs.file(embedderAsset)
    doLast {
        val f = embedderAsset.asFile
        if (!f.exists()) {
            f.parentFile.mkdirs()
            URI("https://storage.googleapis.com/mediapipe-models/text_embedder/universal_sentence_encoder/float32/latest/universal_sentence_encoder.tflite")
                .toURL().openStream().use { input -> f.outputStream().use { input.copyTo(it) } }
        }
    }
}
tasks.named("preBuild") { dependsOn(downloadEmbedder) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.00")
    implementation(composeBom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.google.mediapipe:tasks-genai:0.10.35")
    implementation("com.google.mediapipe:tasks-text:0.10.35")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
}
