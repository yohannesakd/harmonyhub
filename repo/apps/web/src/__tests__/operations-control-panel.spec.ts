import { mount } from '@vue/test-utils'

import OperationsControlPanel from '@/components/operations/OperationsControlPanel.vue'

describe('OperationsControlPanel', () => {
  it('emits export, backup, drill, and audit requests', async () => {
    const wrapper = mount(OperationsControlPanel, {
      props: {
        loading: false,
        acting: false,
        status: {
          pending_import_batches: 1,
          open_import_duplicates: 2,
          pickup_queue_count: 3,
          delivery_queue_count: 4,
          order_conflict_count: 0,
          latest_backup: null,
          latest_recovery_drill: null,
          audit_retention: {
            retention_days: 365,
            cutoff_at: new Date().toISOString(),
            events_older_than_retention: 0,
          },
          recovery_drill_compliance: {
            interval_days: 90,
            status: 'overdue',
            latest_performed_at: null,
            due_at: null,
            days_until_due: null,
            days_overdue: 90,
          },
        },
        auditEvents: [],
        exportRuns: [
          {
            id: 'export-1',
            export_type: 'directory.csv',
            status: 'completed',
            include_sensitive: false,
            row_count: 10,
            file_size_bytes: 2048,
            sha256: 'abc1234567890',
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ],
        backupRuns: [
          {
            id: 'backup-1',
            trigger_type: 'manual',
            status: 'completed',
            file_path: '/tmp/backup.json',
            file_size_bytes: 4096,
            sha256: 'ff0011223344',
            offline_copy_path: '/tmp/offline.json',
            offline_copy_verified: true,
            verification_json: { checksum_algorithm: 'sha256' },
            error_message: null,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ],
        recoveryDrills: [],
        canViewAudit: true,
        canManageExports: true,
        canManageBackups: true,
        canManageRecoveryDrills: true,
      },
    })

    const exportButton = wrapper
      .findAll('button')
      .find((button) => button.text().toLowerCase().includes('generate directory csv'))
    expect(exportButton).toBeTruthy()
    await exportButton!.trigger('click')
    expect(wrapper.emitted('runExport')?.[0][0]).toBe(false)

    const backupCheckbox = wrapper.findAll('input[type="checkbox"]')[1]
    await backupCheckbox.setValue(false)
    const backupButton = wrapper
      .findAll('button')
      .find((button) => button.text().toLowerCase().includes('run backup now'))
    expect(backupButton).toBeTruthy()
    await backupButton!.trigger('click')
    expect(wrapper.emitted('runBackup')?.[0][0]).toBe(false)

    const scenarioInput = wrapper.find('input[placeholder="e.g. restore latest and verify records"]')
    await scenarioInput.setValue('restore latest and verify queues')
    const drillButton = wrapper
      .findAll('button')
      .find((button) => button.text().toLowerCase().includes('record drill'))
    expect(drillButton).toBeTruthy()
    await drillButton!.trigger('click')
    expect(wrapper.emitted('recordDrill')?.[0][0]).toMatchObject({
      scenario: 'restore latest and verify queues',
      status: 'passed',
    })

    const actionPrefixInput = wrapper.find('input[placeholder="e.g. exports."]')
    await actionPrefixInput.setValue('exports.')
    const targetTypeInput = wrapper.find('input[placeholder="e.g. backup_run"]')
    await targetTypeInput.setValue('backup_run')

    const applyButton = wrapper
      .findAll('button')
      .find((button) => button.text().toLowerCase().includes('apply filters'))
    expect(applyButton).toBeTruthy()
    await applyButton!.trigger('click')
    expect(wrapper.emitted('requestAudit')?.[0][0]).toMatchObject({
      action_prefix: 'exports.',
      target_type: 'backup_run',
      limit: 100,
    })

    expect(wrapper.text()).toContain('Recovery drill compliance')
    expect(wrapper.text()).toContain('overdue')
    expect(wrapper.text()).toContain('Audit retention policy')
  })
})
