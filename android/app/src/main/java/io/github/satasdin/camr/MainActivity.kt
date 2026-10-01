package io.github.satasdin.camr

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import io.github.satasdin.camr.ui.CamrApp
import io.github.satasdin.camr.ui.CamrTheme
import io.github.satasdin.camr.ui.CamrViewModel

class MainActivity : ComponentActivity() {
    private val vm: CamrViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        handleShare(intent)
        setContent { CamrTheme { CamrApp(vm) } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    /** "Share → CAMR" from any app stores the shared text as memory. */
    private fun handleShare(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
            vm.teach(text, intent.getStringExtra(Intent.EXTRA_SUBJECT) ?: "Shared")
        }
    }
}
