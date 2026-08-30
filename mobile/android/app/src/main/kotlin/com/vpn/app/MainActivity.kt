package com.vpn.app

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import androidx.annotation.NonNull
import com.wireguard.android.backend.GoBackend
import com.wireguard.android.backend.Tunnel
import com.wireguard.config.Config
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*
import java.io.BufferedReader
import java.io.ByteArrayInputStream
import java.io.StringReader

class MainActivity : FlutterActivity() {
    private val ENGINE_CHANNEL = "com.vpn.app/engine"
    private val STATUS_CHANNEL = "com.vpn.app/status"
    private val STATS_CHANNEL = "com.vpn.app/stats"
    private val VPN_REQUEST_CODE = 1001

    private var pendingVpnConfig: String? = null
    private var pendingResult: MethodChannel.Result? = null

    private var backend: GoBackend? = null
    private val tunnel = object : Tunnel {
        override fun getName(): String = "nova_vpn"
        override fun onStateChange(state: Tunnel.State) {
            val statusStr = when (state) {
                Tunnel.State.UP -> "CONNECTED"
                Tunnel.State.DOWN -> "DISCONNECTED"
                Tunnel.State.TOGGLE -> "CONNECTING"
            }
            isConnected = (state == Tunnel.State.UP)
            runOnUiThread {
                statusSink?.success(statusStr)
            }
        }
    }

    private val activityScope = CoroutineScope(Dispatchers.Main + Job())
    private var statsJob: Job? = null

    companion object {
        var statusSink: EventChannel.EventSink? = null
        var statsSink: EventChannel.EventSink? = null
        var isConnected: Boolean = false
    }

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        try {
            backend = GoBackend(this)
        } catch (e: Exception) {
            e.printStackTrace()
        }

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
                        connectTunnel(config, result)
                    }
                }
                "stopVpn" -> {
                    disconnectTunnel(result)
                }
                "getTunnelState" -> {
                    val state = if (isConnected) "CONNECTED" else "DISCONNECTED"
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
                    statusSink?.success(if (isConnected) "CONNECTED" else "DISCONNECTED")
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
                val config = pendingVpnConfig!!
                val res = pendingResult
                connectTunnel(config, res)
            } else {
                pendingResult?.error("PERMISSION_DENIED", "User denied VPN permission", null)
            }
            pendingVpnConfig = null
            pendingResult = null
        }
    }

    private fun connectTunnel(rawConfig: String, result: MethodChannel.Result?) {
        activityScope.launch(Dispatchers.IO) {
            try {
                val sanitizedConfigStr = sanitizeWireGuardConfig(rawConfig)
                val config = Config.parse(ByteArrayInputStream(sanitizedConfigStr.toByteArray()))
                
                backend?.setState(tunnel, Tunnel.State.UP, config)
                isConnected = true

                withContext(Dispatchers.Main) {
                    statusSink?.success("CONNECTED")
                    result?.success(true)
                    startStatsMonitoring()
                }
            } catch (e: Exception) {
                e.printStackTrace()
                withContext(Dispatchers.Main) {
                    isConnected = false
                    statusSink?.success("ERROR")
                    result?.error("TUNNEL_ERROR", e.message ?: "Failed to start tunnel", null)
                }
            }
        }
    }

    private fun disconnectTunnel(result: MethodChannel.Result?) {
        activityScope.launch(Dispatchers.IO) {
            try {
                statsJob?.cancel()
                backend?.setState(tunnel, Tunnel.State.DOWN, null)
                isConnected = false

                withContext(Dispatchers.Main) {
                    statusSink?.success("DISCONNECTED")
                    result?.success(true)
                }
            } catch (e: Exception) {
                e.printStackTrace()
                withContext(Dispatchers.Main) {
                    result?.error("DISCONNECT_ERROR", e.message, null)
                }
            }
        }
    }

    private fun startStatsMonitoring() {
        statsJob?.cancel()
        statsJob = activityScope.launch(Dispatchers.IO) {
            while (isActive && isConnected) {
                try {
                    val stats = backend?.getStatistics(tunnel)
                    if (stats != null) {
                        val rx = stats.totalRx()
                        val tx = stats.totalTx()
                        withContext(Dispatchers.Main) {
                            statsSink?.success(mapOf("rx" to rx, "tx" to tx))
                        }
                    }
                } catch (_: Exception) {}
                delay(1000)
            }
        }
    }

    private fun sanitizeWireGuardConfig(config: String): String {
        val validInterfaceKeys = setOf("privatekey", "address", "dns", "mtu", "listenport")
        val validPeerKeys = setOf("publickey", "presharedkey", "allowedips", "endpoint", "persistentkeepalive")

        val sb = StringBuilder()
        var currentSection = ""

        BufferedReader(StringReader(config)).useLines { lines ->
            for (rawLine in lines) {
                val line = rawLine.trim()
                if (line.startsWith("[") && line.endsWith("]")) {
                    currentSection = line.substring(1, line.length - 1).toLowerCase()
                    sb.append(rawLine).append("\n")
                    continue
                }

                val equalsIdx = line.indexOf('=')
                if (equalsIdx != -1) {
                    val key = line.substring(0, equalsIdx).trim().toLowerCase()
                    when (currentSection) {
                        "interface" -> {
                            if (validInterfaceKeys.contains(key)) {
                                sb.append(rawLine).append("\n")
                            }
                        }
                        "peer" -> {
                            if (validPeerKeys.contains(key)) {
                                sb.append(rawLine).append("\n")
                            }
                        }
                        else -> {
                            sb.append(rawLine).append("\n")
                        }
                    }
                }
            }
        }
        return sb.toString()
    }

    override fun onDestroy() {
        activityScope.cancel()
        super.onDestroy()
    }
}
