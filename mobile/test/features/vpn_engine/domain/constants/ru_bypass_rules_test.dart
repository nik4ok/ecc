import 'package:flutter_test/flutter_test.dart';
import 'package:vpn_app/features/vpn_engine/domain/constants/ru_bypass_rules.dart';

void main() {
  group('RuBypassRules.androidPackages', () {
    test('includes Госуслуги, ФНС, Ozon and Wildberries apps', () {
      expect(RuBypassRules.androidPackages, containsAll(<String>[
        'ru.gosuslugi.mobile',
        'ru.fns.lkfl',
        'ru.ozon.app.android',
        'com.wildberries.ru',
      ]));
    });

    test('includes the most used RU banks, marketplaces and Yandex apps', () {
      expect(RuBypassRules.androidPackages, containsAll(<String>[
        'ru.sberbankmobile',
        'com.idamob.tinkoff.android',
        'ru.vtb24.mobilebanking.android',
        'ru.alfabank.mobile.android',
        'com.avito.android',
        'com.vkontakte.android',
        'ru.yandex.market',
        'ru.mos.droid',
      ]));
    });

    test('does not bypass browsers or the keyboard (would leak all destinations)', () {
      expect(RuBypassRules.androidPackages, isNot(contains('com.yandex.browser')));
      expect(RuBypassRules.androidPackages, isNot(contains('ru.yandex.androidkeyboard')));
      expect(RuBypassRules.androidPackages, isNot(contains('com.android.chrome')));
    });
  });

  group('RuBypassRules.domains', () {
    test('covers state portals and major marketplaces', () {
      expect(RuBypassRules.domains, containsAll(<String>[
        'gosuslugi.ru',
        'nalog.gov.ru',
        'nalog.ru',
        'ozon.ru',
        'wildberries.ru',
        'wb.ru',
        'avito.ru',
        'mos.ru',
      ]));
    });
  });

  group('RuBypassRules.configComment', () {
    test('encodes sorted packages when split tunneling is on', () {
      final comment = RuBypassRules.configComment(enabled: true);
      expect(comment, startsWith('# nova_bypass_packages='));
      expect(comment, contains('ru.gosuslugi.mobile'));
      expect(comment, contains('ru.ozon.app.android'));
      expect(comment, contains('com.wildberries.ru'));
      expect(comment, isNot(contains('\n')));
    });

    test('is empty when split tunneling is off', () {
      expect(RuBypassRules.configComment(enabled: false), isEmpty);
    });
  });

  group('RuBypassRules.packagesFromConfig', () {
    test('round-trips the encoded comment', () {
      final comment = RuBypassRules.configComment(enabled: true);
      final config = '$comment\nprivate_key=abc\n';
      final packages = RuBypassRules.packagesFromConfig(config);
      expect(packages.toSet(), RuBypassRules.androidPackages);
    });

    test('returns empty when the marker is missing', () {
      expect(
        RuBypassRules.packagesFromConfig('# nova_address=10.8.1.2\nprivate_key=abc\n'),
        isEmpty,
      );
    });
  });
}
