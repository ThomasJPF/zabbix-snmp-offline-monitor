<?php

namespace Modules\SNMPMonitor;

use Zabbix\Core\CModule,
    APP,
    CMenu,
    CMenuItem;

class Module extends CModule {

    public function init(): void {
        APP::Component()->get('menu.main')
            ->findOrAdd(_('Monitoring'))
            ->getSubmenu()
            ->insertAfter(_('Discovery'),
                (new CMenuItem(_('SNMP Monitor')))->setSubMenu(
                    new CMenu([
                        (new CMenuItem(_('Dashboard')))->setAction('snmp.monitor'),
                        (new CMenuItem(_('Export Report')))->setAction('snmp.monitor.download')
                    ])
                )
            );
    }
} 