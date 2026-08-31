package com.vpn.app.service

import android.content.Context
import com.getkeepsafe.relinker.ReLinker
import org.amnezia.awg.GoBackend
import org.amnezia.awg.config.Config
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Thin wrapper around public JNI in org.amnezia.awg.GoBackend (amneziawg-android 2.3.7):
 *   public static native int awgTurnOn(String ifName, int tunFd, String settings, String uapiPath)
 *   public static native void awgTurnOff(int handle)
 *   public static native int awgGetSocketV4(int handle)
 *   public static native int awgGetSocketV6(int handle)
 *   public static native String awgGetConfig(int handle)
 *   public static native String awgVersion()
 *
 * Native library name: libam-go.so
 */
object AwgGoJni {
    private const val NATIVE_LIB = "am-go"
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

    fun toGoSettings(ini: String): String {
        val parsed = Config.parse(ini.byteInputStream(Charsets.UTF_8))
        // Endpoint is already IPv4; skip DoH/okhttp resolution (excluded at Gradle).
        return parsed.toAwgQuickString(false, false)
    }

    fun turnOn(ifName: String, tunFd: Int, settings: String, uapiPath: String): Int {
        return GoBackend.awgTurnOn(ifName, tunFd, settings, uapiPath)
    }

    fun turnOff(handle: Int) {
        GoBackend.awgTurnOff(handle)
    }

    fun getSocketV4(handle: Int): Int = GoBackend.awgGetSocketV4(handle)

    fun getSocketV6(handle: Int): Int = GoBackend.awgGetSocketV6(handle)

    fun getConfig(handle: Int): String? = GoBackend.awgGetConfig(handle)
}
