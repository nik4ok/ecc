package com.vpn.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.TrafficStats
import android.net.VpnService
import android.os.Handler
import android.os.Looper
import androidx.annotation.NonNull
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

    private var pendingVpnConfig: String? = null
    private var pendingResult: MethodChannel.Result? = null

    private val activityScope = CoroutineScope(Dispatchers.Main + Job())
    private var statsJob: Job? = null

    companion object {
        private val mainHandler = Handler(Looper.getMainLooper())
        var statusSink: EventChannel.EventSink? = null
        var statsSink: EventChannel.EventSink? = null

        var isConnected: Boolean
            get() = NovaVpnService.isRunning
            set(value) {
                // Synchronized with NovaVpnService
            }

        fun sendStatus(status: String) {
            mainHandler.post {
                statusSink?.success(status)
            }
        }
    }

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // MethodChannel for VPN management commands
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, ENGINE_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startVpn" -> {
                    val config = call.argument<String>("config") ?: ""
                    prepareAndStartVpn(config, result)
                }
                "stopVpn" -> {
                    stopVpnService(result)
                }
                "getTunnelState" -> {
                    val state = if (NovaVpnService.isRunning) "CONNECTED" else "DISCONNECTED"
                    result.success(state)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }

        // EventChannel for connection status
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, STATUS_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    statusSink = events
                    val initialState = if (NovaVpnService.isRunning) "CONNECTED" else "DISCONNECTED"
                    sendStatus(initialState)
                }

                override fun onCancel(arguments: Any?) {
                    statusSink = null
                }
            }
        )

        // EventChannel for network traffic stats (Rx / Tx)
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
        val vpnIntent = VpnService.prepare(this)
        if (vpnIntent != null) {
            pendingVpnConfig = config
            pendingResult = result
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
                val config = pendingVpnConfig ?: ""
                startVpnService(config)
                pendingResult?.success(true)
            } else {
                sendStatus("DISCONNECTED")
                pendingResult?.error("PERMISSION_DENIED", "Пользователь отклонил VPN-разрешение", null)
            }
            pendingVpnConfig = null
            pendingResult = null
        }
    }

    private fun startVpnService(config: String) {
        sendStatus("CONNECTING")
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_CONNECT
            putExtra(NovaVpnService.EXTRA_CONFIG, config)
        }
        ContextCompat.startForegroundService(this, intent)
        startStatsMonitoring()
    }

    private fun stopVpnService(result: MethodChannel.Result?) {
        stopStatsMonitoring()
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_DISCONNECT
        }
        startService(intent)
        result?.success(true)
    }

    private fun startStatsMonitoring() {
        statsJob?.cancel()
        statsJob = activityScope.launch(Dispatchers.IO) {
            var lastRx = TrafficStats.getTotalRxBytes()
            var lastTx = TrafficStats.getTotalTxBytes()

            while (isActive && NovaVpnService.isRunning) {
                delay(1000)
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
