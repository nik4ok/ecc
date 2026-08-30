import UIKit
import Flutter
import NetworkExtension

@UIApplicationMain
@objc class AppDelegate: FlutterAppDelegate {
  private let ENGINE_CHANNEL = "com.vpn.app/engine"
  private let STATUS_CHANNEL = "com.vpn.app/status"
  private let STATS_CHANNEL = "com.vpn.app/stats"

  private var statusSink: FlutterEventSink?
  private var statsSink: FlutterEventSink?
  private var isConnected: Bool = false

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    let controller : FlutterViewController = window?.rootViewController as! FlutterViewController

    let engineChannel = FlutterMethodChannel(name: ENGINE_CHANNEL, binaryMessenger: controller.binaryMessenger)
    engineChannel.setMethodCallHandler({ [weak self] (call: FlutterMethodCall, result: @escaping FlutterResult) -> Void in
      guard let self = self else { return }
      
      switch call.method {
      case "startVpn":
        self.isConnected = true
        self.statusSink?("CONNECTED")
        result(true)
      case "stopVpn":
        self.isConnected = false
        self.statusSink?("DISCONNECTED")
        result(true)
      case "getTunnelState":
        result(self.isConnected ? "CONNECTED" : "DISCONNECTED")
      default:
        result(FlutterMethodNotImplemented)
      }
    })

    let statusEventChannel = FlutterEventChannel(name: STATUS_CHANNEL, binaryMessenger: controller.binaryMessenger)
    statusEventChannel.setStreamHandler(StatusStreamHandler(parent: self))

    let statsEventChannel = FlutterEventChannel(name: STATS_CHANNEL, binaryMessenger: controller.binaryMessenger)
    statsEventChannel.setStreamHandler(StatsStreamHandler(parent: self))

    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  class StatusStreamHandler: NSObject, FlutterStreamHandler {
    weak var parent: AppDelegate?
    init(parent: AppDelegate) { self.parent = parent }

    func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
      parent?.statusSink = events
      events(parent?.isConnected == true ? "CONNECTED" : "DISCONNECTED")
      return nil
    }

    func onCancel(withArguments arguments: Any?) -> FlutterError? {
      parent?.statusSink = nil
      return nil
    }
  }

  class StatsStreamHandler: NSObject, FlutterStreamHandler {
    weak var parent: AppDelegate?
    init(parent: AppDelegate) { self.parent = parent }

    func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
      parent?.statsSink = events
      return nil
    }

    func onCancel(withArguments arguments: Any?) -> FlutterError? {
      parent?.statsSink = nil
      return nil
    }
  }
}
