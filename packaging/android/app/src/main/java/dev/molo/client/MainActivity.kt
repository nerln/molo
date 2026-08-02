package dev.molo.client

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Context
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

/**
 * Client Android di Molo.
 *
 * Non scarica niente da solo: mostra l'interfaccia dell'istanza che gira sul
 * computer, sulla tua rete locale. La scelta è deliberata. Far girare yt-dlp
 * dentro un'app Android richiede di impacchettare un interprete Python
 * (è quello che fa la libreria youtubedl-android), e quel lavoro lo fanno già
 * bene Seal e YTDLnis. Duplicarlo peggio non aiuta nessuno.
 *
 * Se vuoi Molo autonomo sul telefono, senza computer acceso, c'è la strada
 * Termux: scripts/termux-install.sh.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        web = WebView(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true   // sessionStorage tiene il token
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = WebViewClient()
            webChromeClient = WebChromeClient()
        }
        setContentView(web)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })

        val saved = prefs().getString(KEY_URL, null)
        if (saved.isNullOrBlank()) askForServer() else web.loadUrl(saved)
    }

    /** Il link di accoppiamento sta nelle impostazioni di Molo sul computer. */
    private fun askForServer() {
        val input = EditText(this).apply {
            hint = "http://192.168.1.10:7788/?token=..."
            setSingleLine()
        }
        AlertDialog.Builder(this)
            .setTitle("Indirizzo di Molo")
            .setMessage(
                "Sul computer apri Molo → Impostazioni, attiva «Raggiungibile dal " +
                    "telefono» e copia il link. Incollalo qui."
            )
            .setView(input)
            .setCancelable(false)
            .setPositiveButton("Collega") { _, _ ->
                val url = input.text.toString().trim()
                if (url.isEmpty()) {
                    Toast.makeText(this, "Serve un indirizzo", Toast.LENGTH_SHORT).show()
                    askForServer()
                } else {
                    val full = if (url.startsWith("http")) url else "http://$url"
                    prefs().edit().putString(KEY_URL, full).apply()
                    web.loadUrl(full)
                }
            }
            .setNeutralButton("Esci") { _, _ -> finish() }
            .show()
    }

    private fun prefs() = getSharedPreferences("molo", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_URL = "server_url"
    }
}
