package com.vpn.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.core.app.NotificationCompat
import com.vpn.app.MainActivity
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

class NovaVpnService : VpnService() {

    companion object {
        const val ACTION_CONNECT = "com.vpn.app.service.CONNECT"
        const val ACTION_DISCONNECT = "com.vpn.app.service.DISCONNECT"
        const val EXTRA_CONFIG = "vpn_config"
        private const val TAG = "NovaVpnService"
        private const val NOTIFICATION_CHANNEL_ID = "nova_vpn_channel"
        private const val NOTIFICATION_ID = 101
        private const val TUNNEL_IFACE = "nova0"
        private const val HANDSHAKE_TIMEOUT_MS = 15_000L
        private const val HANDSHAKE_POLL_MS = 500L

        @Volatile
        var nativeStatus: String = "DISCONNECTED"
            private set

        @Volatile
        var isRunning: Boolean = false
            private set

        private fun publishStatus(status: String) {
            nativeStatus = status
            isRunning = status == "CONNECTED" ||
                status == "HANDSHAKING" ||
                status == "CONNECTING"
            MainActivity.sendStatus(status)
        }
    }

    private val engineLock = Any()
    private val sessionSeq = AtomicInteger(0)
    private val engineExecutor = Executors.newSingleThreadExecutor()
    private var vpnInterface: ParcelFileDescriptor? = null
    private var tunFdDetached: Boolean = false
    private var tunnelHandle: Int = -1

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            return START_STICKY
        }

        when (intent.action) {
            ACTION_CONNECT -> {
                val config = intent.getStringExtra(EXTRA_CONFIG) ?: ""
                startTunnel(config)
            }
            ACTION_DISCONNECT -> {
                stopTunnel(notify = true)
                return START_NOT_STICKY
            }
            else -> return START_NOT_STICKY
        }

        return if (isRunning) START_STICKY else START_NOT_STICKY
    }

    private fun startTunnel(config: String) {
        try {
            shutdownEngine()
            publishStatus("CONNECTING")
            val notification = createNotification("NOVA VPN — Подключаемся...")
            promoteToForeground(notification)

            // Parse and resolve while the default network still exists.
            // After establish() DNS would fall into an empty tun0.
            AwgGoJni.load(this)
            val goSettings = AwgGoJni.toGoSettings(config)

            val clientIp = extractClientIp(config) ?: "10.8.1.2"
            val builder = Builder()
                .setSession("NOVA")
                .setMtu(1360)
                .addAddress(clientIp, 32)
                .addDnsServer("1.1.1.1")
                .addDnsServer("8.8.8.8")
                .addRoute("0.0.0.0", 0)
                .setBlocking(false)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                builder.setMetered(false)
            }

            applyBypassPackages(builder, config)

            val configureIntent = Intent(this, MainActivity::class.java)
            val pendingIntent = PendingIntent.getActivity(
                this, 0, configureIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.setConfigureIntent(pendingIntent)

            val established = builder.establish()
            if (established == null) {
                Log.e(TAG, "VpnService.Builder.establish() returned null")
                stopTunnel(notify = true, error = true)
                return
            }

            synchronized(engineLock) {
                vpnInterface = established
                tunFdDetached = false
            }

            val session = sessionSeq.incrementAndGet()
            engineExecutor.execute {
                bringUpEngine(goSettings, session)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start VPN tunnel: ${e.javaClass.simpleName}")
            stopTunnel(notify = true, error = true)
        }
    }

    private fun bringUpEngine(goSettings: String, session: Int) {
        var detachedFd: Int? = null
        try {
            if (session != sessionSeq.get()) {
                return
            }

            val fd: Int
            synchronized(engineLock) {
                if (session != sessionSeq.get()) {
                    return
                }
                val pfd = vpnInterface ?: throw IllegalStateException("TUN interface missing")
                fd = pfd.detachFd()
                tunFdDetached = true
                detachedFd = fd
                vpnInterface = null
            }

            val handle = AwgGoJni.turnOn(TUNNEL_IFACE, fd, goSettings)
            if (handle < 0) {
                Log.e(TAG, "awgTurnOn failed with handle=$handle")
                closeDetachedFd(fd)
                detachedFd = null
                if (session == sessionSeq.get()) {
                    failEngine()
                }
                return
            }
            detachedFd = null

            synchronized(engineLock) {
                if (session != sessionSeq.get()) {
                    AwgGoJni.turnOff(handle)
                    return
                }
                tunnelHandle = handle
            }

            protectSocket(AwgGoJni.getSocketV4(handle))
            protectSocket(AwgGoJni.getSocketV6(handle))

            publishStatus("HANDSHAKING")
            updateNotification("NOVA VPN — Рукопожатие...")

            val handshakeOk = waitForHandshake(handle, session)
            if (session != sessionSeq.get()) {
                return
            }
            if (handshakeOk) {
                publishStatus("CONNECTED")
                updateNotification("NOVA VPN — Защита активна")
                Log.i(TAG, "AmneziaWG handshake complete")
            } else {
                Log.e(TAG, "AmneziaWG handshake timed out")
                failEngine()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to bring up AmneziaWG engine: ${e.javaClass.simpleName}")
            detachedFd?.let { closeDetachedFd(it) }
            if (session == sessionSeq.get()) {
                failEngine()
            }
        }
    }

    private fun closeDetachedFd(fd: Int) {
        try {
            ParcelFileDescriptor.adoptFd(fd).close()
        } catch (e: Exception) {
            Log.w(TAG, "Closing detached TUN fd failed: ${e.javaClass.simpleName}")
        }
    }

    private fun waitForHandshake(handle: Int, session: Int): Boolean {
        val deadline = System.currentTimeMillis() + HANDSHAKE_TIMEOUT_MS
        while (System.currentTimeMillis() < deadline) {
            if (session != sessionSeq.get()) {
                return false
            }
            if (hasCompletedHandshake(AwgGoJni.getConfig(handle))) {
                return true
            }
            try {
                Thread.sleep(HANDSHAKE_POLL_MS)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return false
            }
        }
        return hasCompletedHandshake(AwgGoJni.getConfig(handle))
    }

    private fun hasCompletedHandshake(uapiConfig: String?): Boolean {
        if (uapiConfig.isNullOrEmpty()) {
            return false
        }
        for (line in uapiConfig.split('\n')) {
            if (line.startsWith("last_handshake_time_sec=")) {
                val value = line.substringAfter('=').trim().toLongOrNull() ?: 0L
                if (value > 0L) {
                    return true
                }
            }
        }
        return false
    }

    private fun protectSocket(socketFd: Int) {
        if (socketFd >= 0) {
            protect(socketFd)
        }
    }

    private fun failEngine() {
        stopTunnel(notify = true, error = true)
    }

    private fun promoteToForeground(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun shutdownEngine() {
        sessionSeq.incrementAndGet()
        synchronized(engineLock) {
            if (tunnelHandle >= 0) {
                try {
                    AwgGoJni.turnOff(tunnelHandle)
                } catch (e: Exception) {
                    Log.w(TAG, "awgTurnOff failed", e)
                }
                tunnelHandle = -1
            }
            if (!tunFdDetached) {
                try {
                    vpnInterface?.close()
                } catch (e: Exception) {
                    Log.w(TAG, "Error closing TUN interface", e)
                }
            }
            vpnInterface = null
            tunFdDetached = false
        }
    }

    private fun stopTunnel(notify: Boolean, error: Boolean = false) {
        shutdownEngine()
        nativeStatus = if (error) "ERROR" else "DISCONNECTED"
        isRunning = false
        if (notify) {
            MainActivity.sendStatus(nativeStatus)
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun applyBypassPackages(builder: Builder, config: String) {
        val packages = extractBypassPackages(config)
        if (packages.isEmpty()) {
            return
        }
        var applied = 0
        for (pkg in packages) {
            if (pkg == packageName) {
                continue
            }
            try {
                builder.addDisallowedApplication(pkg)
                applied += 1
            } catch (e: PackageManager.NameNotFoundException) {
                Log.d(TAG, "bypass skip, not installed: $pkg")
            }
        }
        Log.i(TAG, "split-tunnel bypass apps applied=$applied of ${packages.size}")
    }

    private fun extractBypassPackages(config: String): List<String> {
        val match = Regex("""#\s*nova_bypass_packages=([^\n]+)""").find(config)
            ?: return emptyList()
        return match.groupValues[1]
            .split(',')
            .map { it.trim() }
            .filter { it.isNotEmpty() }
    }

    private fun extractClientIp(config: String): String? {
        val novaAddress = Regex("""#\s*nova_address=([0-9.]+)""")
        novaAddress.find(config)?.groupValues?.getOrNull(1)?.let { return it }
        val addressRegex = Regex("""Address\s*=\s*([0-9.]+)(?:/[0-9]+)?""")
        return addressRegex.find(config)?.groupValues?.getOrNull(1)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "NOVA VPN Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Уведомления о статусе защищенного VPN-соединения"
                setShowBadge(false)
            }
            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(content: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setContentTitle("NOVA")
            .setContentText(content)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .build()
    }

    private fun updateNotification(content: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, createNotification(content))
    }

    override fun onRevoke() {
        stopTunnel(notify = true, error = true)
        super.onRevoke()
    }

    override fun onDestroy() {
        if (isRunning || vpnInterface != null || tunnelHandle >= 0) {
            stopTunnel(notify = true)
        }
        engineExecutor.shutdownNow()
        super.onDestroy()
    }
}
