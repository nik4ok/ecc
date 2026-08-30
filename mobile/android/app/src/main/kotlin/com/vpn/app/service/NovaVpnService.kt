package com.vpn.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.core.app.NotificationCompat
import com.vpn.app.MainActivity

class NovaVpnService : VpnService() {

    companion object {
        const val ACTION_CONNECT = "com.vpn.app.service.CONNECT"
        const val ACTION_DISCONNECT = "com.vpn.app.service.DISCONNECT"
        const val EXTRA_CONFIG = "vpn_config"
        private const val TAG = "NovaVpnService"
        private const val NOTIFICATION_CHANNEL_ID = "nova_vpn_channel"
        private const val NOTIFICATION_ID = 101

        @Volatile
        var isRunning: Boolean = false
            private set
    }

    private var vpnInterface: ParcelFileDescriptor? = null

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
            val notification = createNotification("NOVA VPN — Защита активна")
            promoteToForeground(notification)

            vpnInterface?.close()
            vpnInterface = null

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

            val configureIntent = Intent(this, MainActivity::class.java)
            val pendingIntent = PendingIntent.getActivity(
                this, 0, configureIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.setConfigureIntent(pendingIntent)

            vpnInterface = builder.establish()

            if (vpnInterface != null) {
                isRunning = true
                MainActivity.sendStatus("CONNECTED")
            } else {
                Log.e(TAG, "VpnService.Builder.establish() returned null")
                stopTunnel(notify = true, error = true)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start VPN tunnel", e)
            stopTunnel(notify = true, error = true)
        }
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

    private fun stopTunnel(notify: Boolean, error: Boolean = false) {
        try {
            vpnInterface?.close()
        } catch (e: Exception) {
            Log.w(TAG, "Error closing TUN interface", e)
        }
        vpnInterface = null
        isRunning = false

        if (notify) {
            MainActivity.sendStatus(if (error) "ERROR" else "DISCONNECTED")
        }

        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun extractClientIp(config: String): String? {
        val addressRegex = Regex("""Address\s*=\s*([0-9.]+)(?:/[0-9]+)?""")
        val match = addressRegex.find(config)
        return match?.groupValues?.getOrNull(1)
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

    override fun onRevoke() {
        stopTunnel(notify = true, error = true)
        super.onRevoke()
    }

    override fun onDestroy() {
        if (isRunning || vpnInterface != null) {
            stopTunnel(notify = true)
        }
        super.onDestroy()
    }
}
