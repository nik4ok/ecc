import '../entities/vpn_profile.dart';
import '../entities/amnezia_wg_params.dart';

class DefaultNodes {
  static const VpnProfile netherlandsAmneziaWg = VpnProfile(
    id: "srv-nl-awg-01",
    name: "Нидерланды (Амстердам)",
    serverAddress: "92.51.46.12",
    serverPort: 38037,
    protocolType: VpnProtocolType.amneziaWg,
    publicKey: "dn+S2ksWUSFdjL69a8Q2rk+cBhV6Nt+YOAM2QVwmpAQ=",
    clientAddress: "10.8.1.1/32",
    presharedKey: "8uz3Nv8CoCOp/m7X6eoA02j6n7xKWPH0MahnzrvlhU8=",
    amneziaParams: AmneziaWgParams(
      jc: 5,
      jmin: 10,
      jmax: 50,
      s1: 88,
      s2: 89,
      s3: 43,
      s4: 12,
      h1: 1,
      h2: 2,
      h3: 3,
      h4: 4,
      headerProtectionKey: "QIu3Z5Di5xnPXLtB0VgavFJbp/la7s4EBkFOfCSujis=",
    ),
  );
}
