import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PolicyManagementView from '@/views/PolicyManagementView.vue'

const bootstrapWorkspace = vi.fn().mockResolvedValue(undefined)
const switchWorkspaceContext = vi.fn().mockResolvedValue(undefined)

const authStore = {
  permissions: ['abac.policy.manage'],
}

const contextStore = {
  contexts: [],
  activeContext: null,
  switching: false,
  errorMessage: null,
}

vi.mock('@/composables/useWorkspaceContext', () => ({
  useWorkspaceContext: () => ({
    authStore,
    contextStore,
    bootstrapWorkspace,
    switchWorkspaceContext,
  }),
}))

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    listAbacSurfaces: vi.fn(),
    listAbacRules: vi.fn(),
    createAbacRule: vi.fn(),
    deleteAbacRule: vi.fn(),
    simulateAbac: vi.fn(),
    upsertAbacSurface: vi.fn(),
  }
})

import { createAbacRule, listAbacRules, listAbacSurfaces, simulateAbac } from '@/services/api'

function sectionByHeading(wrapper: ReturnType<typeof mount>, heading: string) {
  const section = wrapper
    .findAll('.panel-section')
    .find((candidate) => candidate.find('h3').exists() && candidate.find('h3').text().includes(heading))
  expect(section).toBeTruthy()
  return section!
}

function buttonByText(section: ReturnType<typeof sectionByHeading>, label: string) {
  const button = section.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(button).toBeTruthy()
  return button!
}

describe('PolicyManagementView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(listAbacSurfaces).mockResolvedValue([
      {
        id: 'surface-1',
        organization_id: 'org-1',
        surface: 'directory',
        enabled: true,
      },
    ])
    vi.mocked(listAbacRules).mockResolvedValue([])
    vi.mocked(createAbacRule).mockResolvedValue({
      id: 'rule-1',
      organization_id: 'org-1',
      surface: 'directory',
      action: 'search_row',
      effect: 'allow',
      priority: 10,
      role: 'student',
      subject_department: 'music',
      subject_grade: 'grade_10',
      subject_class: '10A',
      program_id: null,
      event_id: null,
      store_id: null,
      resource_department: 'music',
      resource_grade: 'grade_10',
      resource_class: '10A',
      resource_field: null,
    })
    vi.mocked(simulateAbac).mockResolvedValue({
      allowed: true,
      enforced: true,
      reason: 'abac_rule_allow',
      matched_rule_id: 'rule-1',
    })
  })

  it('submits rule/simulation payloads with department-grade-class dimensions', async () => {
    const wrapper = mount(PolicyManagementView, {
      global: {
        stubs: {
          AppShell: {
            template: '<div><slot /></div>',
          },
        },
      },
    })

    await flushPromises()

    const createSection = sectionByHeading(wrapper, 'Create rule')
    await createSection.get('input[placeholder="e.g. directory"]').setValue('directory')
    await createSection.get('input[placeholder="e.g. view"]').setValue('search_row')
    await createSection.get('input[placeholder="student / staff / administrator"]').setValue('student')
    await createSection.get('[data-testid="rule-subject-department"]').setValue('music')
    await createSection.get('[data-testid="rule-subject-grade"]').setValue('grade_10')
    await createSection.get('[data-testid="rule-subject-class"]').setValue('10A')
    await createSection.get('[data-testid="rule-resource-department"]').setValue('music')
    await createSection.get('[data-testid="rule-resource-grade"]').setValue('grade_10')
    await createSection.get('[data-testid="rule-resource-class"]').setValue('10A')
    await createSection.get('[data-testid="rule-resource-field"]').setValue('email')
    await buttonByText(createSection, 'Create rule').trigger('click')

    expect(createAbacRule).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'directory',
        action: 'search_row',
        role: 'student',
        subject_department: 'music',
        subject_grade: 'grade_10',
        subject_class: '10A',
        resource_department: 'music',
        resource_grade: 'grade_10',
        resource_class: '10A',
        resource_field: 'email',
      }),
    )

    const simulationSection = sectionByHeading(wrapper, 'Simulation')
    await simulationSection.get('input[placeholder="e.g. directory"]').setValue('directory')
    await simulationSection.get('input[placeholder="e.g. view"]').setValue('contact_field_view')
    await simulationSection.get('input[placeholder="student"]').setValue('student')
    await simulationSection.get('[data-testid="sim-subject-department"]').setValue('music')
    await simulationSection.get('[data-testid="sim-subject-grade"]').setValue('grade_10')
    await simulationSection.get('[data-testid="sim-subject-class"]').setValue('10A')
    await simulationSection.get('[data-testid="sim-resource-department"]').setValue('music')
    await simulationSection.get('[data-testid="sim-resource-grade"]').setValue('grade_10')
    await simulationSection.get('[data-testid="sim-resource-class"]').setValue('10A')
    await simulationSection.get('[data-testid="sim-resource-field"]').setValue('email')
    await buttonByText(simulationSection, 'Run simulation').trigger('click')

    expect(simulateAbac).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'directory',
        action: 'contact_field_view',
        role: 'student',
        subject: {
          department: 'music',
          grade: 'grade_10',
          class_code: '10A',
        },
        resource: {
          department: 'music',
          grade: 'grade_10',
          class_code: '10A',
          field: 'email',
        },
      }),
    )
  })
})
