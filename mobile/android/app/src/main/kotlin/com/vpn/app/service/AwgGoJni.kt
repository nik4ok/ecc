package com.vpn.app.service

import android.content.Context
import com.getkeepsafe.relinker.ReLinker
import org.amnezia.awg.GoBackend
import java.util.concurrent.atomic.AtomicBoolean

/**
 * JNI around official AmneziaWG 3 libwg-go.so:
 *   awgTurnOn(ifName, tunFd, uapiSettings)
 * Settings must be userspace UAPI (header_protection_key=hex), not wg-quick INI.
 */
object AwgGoJni {
    private const val NATIVE_LIB = "wg-go"
    private val loaded = AtomicBoolean(false)

    fun load(context: Context) {
        if (loaded.get()) {
            return
        }
        synchronized(this) {
            if (loaded.get()) {
                return
            }
            ReLinker.loadLibrary(context.applicationContext, NATIVE_LIB)
            loaded.set(true)
        }
    }

    fun toGoSettings(payload: String): String {
        val body = payload
            .lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("#") }
            .joinToString("\n")
        val trimmed = body.trim()
        return if (trimmed.endsWith('\n')) trimmed else "$trimmed\n"
    }

    fun turnOn(ifName: String, tunFd: Int, settings: String): Int {
        return GoBackend.awgTurnOn(ifName, tunFd, settings)
    }

    fun turnOff(handle: Int) {
        GoBackend.awgTurnOff(handle)
    }

    fun getSocketV4(handle: Int): Int = GoBackend.awgGetSocketV4(handle)

    fun getSocketV6(handle: Int): Int = GoBackend.awgGetSocketV6(handle)

    fun getConfig(handle: Int): String? = GoBackend.awgGetConfig(handle)
}
