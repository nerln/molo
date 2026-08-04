plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "dev.molo.client"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.molo.client"
        minSdk = 24          // Android 7: copre praticamente tutto il parco installato
        targetSdk = 35
        versionCode = 5
        versionName = "1.0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Nessuna firma di release: senza un keystore la CI produce solo
            // l'APK di debug, che è comunque installabile.
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
}
