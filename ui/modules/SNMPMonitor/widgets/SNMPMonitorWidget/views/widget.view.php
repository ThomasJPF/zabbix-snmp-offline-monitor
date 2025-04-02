<?php
/**
 * Widget SNMP Devices view
 */

// Se houver erro
if (array_key_exists('error', $data)) {
    ?>
    <div class="widget-error">
        <?= $data['error'] ?>
    </div>
    <?php
    return;
}

// Container para o widget
$widget_container = (new CDiv())
    ->addClass('snmp-devices-widget')
    ->addStyle('height: 100%; position: relative; overflow: auto;');

// Lista de hosts
$hosts = $data['hosts'];
$show_ping_status = $data['show_ping_status'];

// HTML para o widget
?>
<div class="dashboard-widget-snmpmonitor" style="height: 100%; overflow: auto;">
    <?php
    if (empty($hosts)) {
        ?>
        <div class="no-data" style="display: flex; align-items: center; justify-content: center; height: 100%; color: #888;">
            <?= _('No SNMP devices found') ?>
        </div>
        <?php
    }
    else {
        ?>
        <table class="list-table" style="width: 100%;">
            <thead>
                <tr>
                    <th><?= _('Host') ?></th>
                    <th><?= _('IP') ?></th>
                    <th><?= _('SNMP Status') ?></th>
                    <?php if ($show_ping_status): ?>
                    <th><?= _('Ping') ?></th>
                    <?php endif; ?>
                    <th><?= _('Error') ?></th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($hosts as $host): ?>
                <tr>
                    <td>
                        <a href="zabbix.php?action=host.view&hostid=<?= $host['hostid'] ?>" target="_blank" title="<?= _('Go to host') ?>">
                            <?= htmlspecialchars($host['name']) ?>
                        </a>
                    </td>
                    <td><?= htmlspecialchars($host['snmp_interface']['ip']) ?></td>
                    <td>
                        <?php if ($host['snmp_status']['status'] === 1): ?>
                            <span class="<?= ZBX_STYLE_GREEN ?>"><?= _('Online') ?></span>
                        <?php elseif ($host['snmp_status']['status'] === 0): ?>
                            <span class="<?= ZBX_STYLE_RED ?>"><?= _('Offline') ?></span>
                        <?php else: ?>
                            <span class="<?= ZBX_STYLE_GREY ?>"><?= _('Unknown') ?></span>
                        <?php endif; ?>
                    </td>
                    <?php if ($show_ping_status): ?>
                    <td>
                        <?php if ($host['ping_status']['status'] === 1): ?>
                            <span class="<?= ZBX_STYLE_GREEN ?>"><?= _('Online') ?></span>
                        <?php elseif ($host['ping_status']['status'] === 0): ?>
                            <span class="<?= ZBX_STYLE_RED ?>"><?= _('Offline') ?></span>
                        <?php else: ?>
                            <span class="<?= ZBX_STYLE_GREY ?>"><?= _('Unknown') ?></span>
                        <?php endif; ?>
                    </td>
                    <?php endif; ?>
                    <td class="snmp-error" title="<?= htmlspecialchars($host['snmp_status']['error'] ?? '') ?>">
                        <?= substr(htmlspecialchars($host['snmp_status']['error'] ?? ''), 0, 50) ?>
                        <?php if (strlen($host['snmp_status']['error'] ?? '') > 50): ?>...<?php endif; ?>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
        <?php
    }
    ?>
</div>

<script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        // Adiciona tooltip para mensagens de erro longas
        const errorCells = document.querySelectorAll('.snmp-error');
        if (typeof jQuery !== 'undefined' && typeof jQuery.fn.tooltip !== 'undefined') {
            jQuery(errorCells).tooltip({
                classes: {
                    'ui-tooltip': 'ui-corner-all tooltip-error'
                }
            });
        }
    });
</script> 