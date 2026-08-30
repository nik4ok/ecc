package com.vpn.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.TrafficStats
import android.net.VpnService
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.annotation.NonNull
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.vpn.app.service.NovaVpnService
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*

class MainActivity : FlutterActivity() {
    private val ENGINE_CHANNEL = "com.vpn.app/engine"
    private val STATUS_CHANNEL = "com.vpn.app/status"
    private val STATS_CHANNEL = "com.vpn.app/stats"
    private val VPN_REQUEST_CODE = 1001
    private val NOTIFICATION_REQUEST_CODE = 1002
    private val PREFS_NAME = "nova_vpn"
    private val PREFS_PENDING_CONFIG = "pending_config"

    private var pendingVpnConfig: String? = null
    private var pendingResult: MethodChannel.Result? = null

    private val activityScope = CoroutineScope(Dispatchers.Main + Job())
    private var statsJob: Job? = null

    companion object {
        private val mainHandler = Handler(Looper.getMainLooper())
        var statusSink: EventChannel.EventSink? = null
        var statsSink: EventChannel.EventSink? = null

        @Volatile
        var isPreparingVpn: Boolean = false

        fun sendStatus(status: String) {
            if (status == "CONNECTED" || status == "DISCONNECTED" || status == "ERROR") {
                isPreparingVpn = false
            }
            mainHandler.post {
                statusSink?.success(status)
            }
        }
    }

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        requestNotificationPermissionIfNeeded()

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, ENGINE_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startVpn" -> {
                    val config = call.argument<String>("config") ?: ""
                    prepareAndStartVpn(config, result)
                }
                "stopVpn" -> {
                    isPreparingVpn = false
                    clearPendingConfig()
                    stopVpnService(result)
                }
                "getTunnelState" -> {
                    val state = when {
                        NovaVpnService.isRunning -> "CONNECTED"
                        isPreparingVpn -> "CONNECTING"
                        else -> "DISCONNECTED"
                    }
                    result.success(state)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, STATUS_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    statusSink = events
                    when {
                        NovaVpnService.isRunning -> sendStatus("CONNECTED")
                        isPreparingVpn -> sendStatus("CONNECTING")
                    }
                }

                override fun onCancel(arguments: Any?) {
                    statusSink = null
                }
            }
        )

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, STATS_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    statsSink = events
                    if (NovaVpnService.isRunning) {
                        startStatsMonitoring()
                    }
                }

                override fun onCancel(arguments: Any?) {
                    statsSink = null
                    stopStatsMonitoring()
                }
            }
        )
    }

    private fun prepareAndStartVpn(config: String, result: MethodChannel.Result) {
        isPreparingVpn = true
        persistPendingConfig(config)
        requestNotificationPermissionIfNeeded()

        val vpnIntent = VpnService.prepare(this)
        if (vpnIntent != null) {
            pendingVpnConfig = config
            sendStatus("CONNECTING")
            // Complete the Flutter future immediately so a permission-dialog
            // Activity recreate cannot fail startTunnel with a lost MethodChannel.Result.
            result.success(true)
            startActivityForResult(vpnIntent, VPN_REQUEST_CODE)
        } else {
            startVpnService(config)
            result.success(true)
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == VPN_REQUEST_CODE) {
            if (resultCode == Activity.RESULT_OK) {
                val config = pendingVpnConfig ?: loadPendingConfig() ?: ""
                startVpnService(config)
            } else {
                isPreparingVpn = false
                clearPendingConfig()
                sendStatus("DISCONNECTED")
            }
            pendingVpnConfig = null
            pendingResult = null
        }
    }

    private fun startVpnService(config: String) {
        isPreparingVpn = true
        sendStatus("CONNECTING")
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_CONNECT
            putExtra(NovaVpnService.EXTRA_CONFIG, config)
        }
        ContextCompat.startForegroundService(this, intent)
        startStatsMonitoring()
        clearPendingConfig()
    }

    private fun stopVpnService(result: MethodChannel.Result?) {
        stopStatsMonitoring()
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_DISCONNECT
        }
        startService(intent)
        result?.success(true)
    }

    private fun persistPendingConfig(config: String) {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putString(PREFS_PENDING_CONFIG, config)
            .apply()
    }

    private fun loadPendingConfig(): String? {
        return getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .getString(PREFS_PENDING_CONFIG, null)
    }

    private fun clearPendingConfig() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .remove(PREFS_PENDING_CONFIG)
            .apply()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.POST_NOTIFICATIONS),
            NOTIFICATION_REQUEST_CODE
        )
    }

    private fun startStatsMonitoring() {
        statsJob?.cancel()
        statsJob = activityScope.launch(Dispatchers.IO) {
            var lastRx = TrafficStats.getTotalRxBytes()
            var lastTx = TrafficStats.getTotalTxBytes()

            while (isActive && (NovaVpnService.isRunning || isPreparingVpn)) {
                delay(1000)
                if (!NovaVpnService.isRunning) {
                    continue
                }
                val currentRx = TrafficStats.getTotalRxBytes()
                val currentTx = TrafficStats.getTotalTxBytes()

                val rxDelta = if (lastRx > 0 && currentRx >= lastRx) currentRx - lastRx else 0L
                val txDelta = if (lastTx > 0 && currentTx >= lastTx) currentTx - lastTx else 0L

                lastRx = currentRx
                lastTx = currentTx

                withContext(Dispatchers.Main) {
                    statsSink?.success(mapOf("rx" to rxDelta, "tx" to txDelta))
                }
            }
        }
    }

    private fun stopStatsMonitoring() {
        statsJob?.cancel()
        statsJob = null
    }

    override fun onDestroy() {
        activityScope.cancel()
        super.onDestroy()
    }
}
