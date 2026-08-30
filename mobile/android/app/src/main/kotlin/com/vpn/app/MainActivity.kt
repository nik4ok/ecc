package com.vpn.app

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import android.os.Build
import androidx.annotation.NonNull
import com.vpn.app.service.NovaVpnService
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val ENGINE_CHANNEL = "com.vpn.app/engine"
    private val STATUS_CHANNEL = "com.vpn.app/status"
    private val STATS_CHANNEL = "com.vpn.app/stats"
    private val VPN_REQUEST_CODE = 1001

    private var pendingVpnConfig: String? = null
    private var pendingResult: MethodChannel.Result? = null

    companion object {
        var statusSink: EventChannel.EventSink? = null
        var statsSink: EventChannel.EventSink? = null
        var isConnected: Boolean = false
    }

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // MethodChannel for commands
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, ENGINE_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startVpn" -> {
                    val config = call.argument<String>("config")
                    if (config == null) {
                        result.error("INVALID_CONFIG", "Config cannot be null", null)
                        return@setMethodCallHandler
                    }

                    val vpnIntent = VpnService.prepare(this)
                    if (vpnIntent != null) {
                        pendingVpnConfig = config
                        pendingResult = result
                        startActivityForResult(vpnIntent, VPN_REQUEST_CODE)
                    } else {
                        startNovaService(config)
                        result.success(true)
                    }
                }
                "stopVpn" -> {
                    stopNovaService()
                    result.success(true)
                }
                "getTunnelState" -> {
                    val state = if (NovaVpnService.isRunning || isConnected) "CONNECTED" else "DISCONNECTED"
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
                    val currentStatus = if (NovaVpnService.isRunning || isConnected) "CONNECTED" else "DISCONNECTED"
                    statusSink?.success(currentStatus)
                }

                override fun onCancel(arguments: Any?) {
                    statusSink = null
                }
            }
        )

        // EventChannel for bandwidth stats
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, STATS_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    statsSink = events
                }

                override fun onCancel(arguments: Any?) {
                    statsSink = null
                }
            }
        )
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == VPN_REQUEST_CODE) {
            if (resultCode == Activity.RESULT_OK && pendingVpnConfig != null) {
                startNovaService(pendingVpnConfig!!)
                pendingResult?.success(true)
            } else {
                pendingResult?.error("PERMISSION_DENIED", "User denied VPN permission", null)
            }
            pendingVpnConfig = null
            pendingResult = null
        }
    }

    private fun startNovaService(config: String) {
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_CONNECT
            putExtra(NovaVpnService.EXTRA_CONFIG, config)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopNovaService() {
        val intent = Intent(this, NovaVpnService::class.java).apply {
            action = NovaVpnService.ACTION_DISCONNECT
        }
        startService(intent)
    }
}
