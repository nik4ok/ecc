class RuBypassRules {
  /// Android apps that stay on the real network when the split-tunnel toggle is on.
  ///
  /// Chrome / other browsers are not in this list: sites opened there still go
  /// through the VPN. Only the native apps below bypass the tunnel.
  static const Set<String> androidPackages = {
    // State
    'ru.gosuslugi.mobile',
    'ru.fns.lkfl',
    'ru.mos.droid',
    'ru.cbr.mobile',
    'ru.pochta.android',
    // Banks and payments
    'ru.sberbankmobile',
    'com.idamob.tinkoff.android',
    'ru.tinkoff.investing',
    'ru.vtb24.mobilebanking.android',
    'ru.alfabank.mobile.android',
    'ru.gazprombank.android.mobilebank.app',
    'org.raiffeisen.android',
    'ru.openbank.digital',
    'ru.rshb.dbo.android.individual',
    'ru.sovcomcard.halva.v1',
    'ru.letobank.Prometheus',
    'ru.mkb.mobile',
    'ru.otpbank.mobile',
    'ru.psbank',
    'ru.mts.money',
    'ru.nspk.mirpay',
    // Marketplaces and shops
    'ru.ozon.app.android',
    'com.wildberries.ru',
    'ru.yandex.market',
    'ru.beru.android',
    'com.avito.android',
    'ru.sbermarket',
    'ru.dns.shop',
    'ru.mvideo.app',
    'ru.citilink',
    'ru.detmir.app',
    'ru.magnit.mobile',
    'ru.pyaterochka.app',
    'ru.x5.perekrestok',
    // Yandex native apps (not the browser or keyboard — those would leak all traffic)
    'ru.yandex.yandexmaps',
    'ru.yandex.yandexnavi',
    'ru.yandex.taxi',
    'ru.yandex.music',
    'ru.yandex.disk',
    'ru.yandex.mail',
    'ru.foodfox',
    // Social and messengers used in RU without a foreign block
    'com.vkontakte.android',
    'ru.ok.android',
    'ru.max',
    // Classifieds / maps / jobs
    'ru.dublgis.dgismobile',
    'ru.cian.main',
    'ru.hh.android',
    // Operators
    'ru.rostel',
    'ru.mts.mtstv',
    'ru.beeline.services',
    'ru.megafon.mlk',
    'ru.tele2.tele2app',
  };

  static const String bypassPackagesMarker = 'nova_bypass_packages';

  /// Domain list for DNS-based split tunneling (iOS and desktop later).
  static const Set<String> domains = {
    'gosuslugi.ru',
    'nalog.gov.ru',
    'nalog.ru',
    'mos.ru',
    'cbr.ru',
    'pochta.ru',
    'sberbank.ru',
    'sber.ru',
    'tbank.ru',
    'tinkoff.ru',
    'vtb.ru',
    'alfabank.ru',
    'ozon.ru',
    'wildberries.ru',
    'wb.ru',
    'avito.ru',
    'ya.ru',
    'yandex.ru',
    'market.yandex.ru',
    'vk.com',
    'ok.ru',
    'max.ru',
    '2gis.ru',
    'cian.ru',
    'hh.ru',
    'nspk.ru',
    'dns-shop.ru',
    'mvideo.ru',
  };

  static String configComment({required bool enabled}) {
    if (!enabled || androidPackages.isEmpty) {
      return '';
    }
    final packages = androidPackages.toList()..sort();
    return '# $bypassPackagesMarker=${packages.join(',')}';
  }

  static String prependToConfig(String config, {required bool enabled}) {
    final comment = configComment(enabled: enabled);
    if (comment.isEmpty) {
      return config;
    }
    return '$comment\n$config';
  }

  static List<String> packagesFromConfig(String config) {
    const prefix = '# $bypassPackagesMarker=';
    for (final rawLine in config.split('\n')) {
      final line = rawLine.trim();
      if (!line.startsWith(prefix)) {
        continue;
      }
      return line
          .substring(prefix.length)
          .split(',')
          .map((item) => item.trim())
          .where((item) => item.isNotEmpty)
          .toList(growable: false);
    }
    return const [];
  }
}
