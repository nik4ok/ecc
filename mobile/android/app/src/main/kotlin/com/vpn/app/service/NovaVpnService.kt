package com.vpn.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import androidx.core.app.NotificationCompat
import com.vpn.app.MainActivity

class NovaVpnService : VpnService() {

    companion object {
        const val ACTION_CONNECT = "com.vpn.app.service.CONNECT"
        const val ACTION_DISCONNECT = "com.vpn.app.service.DISCONNECT"
        const val EXTRA_CONFIG = "vpn_config"
        private const val NOTIFICATION_CHANNEL_ID = "nova_vpn_channel"
        private const val NOTIFICATION_ID = 101

        var isRunning = false
            private set
    }

    private var vpnInterface: ParcelFileDescriptor? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: return START_NOT_STICKY

        when (action) {
            ACTION_CONNECT -> {
                val config = intent.getStringExtra(EXTRA_CONFIG) ?: ""
                startTunnel(config)
            }
            ACTION_DISCONNECT -> {
                stopTunnel()
            }
        }

        return START_NOT_STICKY
    }

    private fun startTunnel(config: String) {
        try {
            // Show foreground notification required by Android
            val notification = createNotification("NOVA VPN — Защита активна")
            startForeground(NOTIFICATION_ID, notification)

            // Close existing interface if open
            vpnInterface?.close()
            vpnInterface = null

            // Parse IP/DNS from config or use defaults
            val clientIp = extractClientIp(config) ?: "10.8.1.2"
            val dnsServer = "1.1.1.1"
            val secondaryDns = "8.8.8.8"
            val mtu = 1360

            // Establish the Android OS VPN Virtual Interface (tun0)
            val builder = Builder()
                .setSession("NOVA")
                .setMtu(mtu)
                .addAddress(clientIp, 32)
                .addDnsServer(dnsServer)
                .addDnsServer(secondaryDns)
                .addRoute("0.0.0.0", 0)

            // Configure intent to open app on notification click
            val configureIntent = Intent(this, MainActivity::class.java)
            val pendingIntent = PendingIntent.getActivity(
                this, 0, configureIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.setConfigureIntent(pendingIntent)

            vpnInterface = builder.establish()

            if (vpnInterface != null) {
                isRunning = true
                MainActivity.isConnected = true
                MainActivity.statusSink?.success("CONNECTED")
            } else {
                stopTunnel()
                MainActivity.statusSink?.success("ERROR")
            }
        } catch (e: Exception) {
            e.printStackTrace()
            stopTunnel()
            MainActivity.statusSink?.success("ERROR")
        }
    }

    private fun stopTunnel() {
        try {
            vpnInterface?.close()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        vpnInterface = null
        isRunning = false
        MainActivity.isConnected = false
        MainActivity.statusSink?.success("DISCONNECTED")

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

    override fun onDestroy() {
        stopTunnel()
        super.onDestroy()
    }
}
