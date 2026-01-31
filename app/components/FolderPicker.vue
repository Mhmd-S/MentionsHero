<template>
  <UFormField label="Save to folder">
    <USelect
      v-model="selectedValue"
      :items="folderOptions"
      label-key="label"
      value-key="value"
      placeholder="Root (no folder)"
      :disabled="disabled"
      class="w-full"
    />

    <div v-if="showNewFolderInput" class="mt-2 space-y-2">
      <p v-if="parentFolderName" class="text-xs text-gray-500">
        Creating subfolder in: {{ parentFolderName }}
      </p>
      <div class="flex gap-2">
        <UInput
          v-model="newFolderName"
          placeholder="Folder name"
          size="sm"
          class="flex-1"
          @keyup.enter="createNewFolder"
          @keyup.escape="cancelNewFolder"
        />
        <UButton size="sm" @click="createNewFolder" :loading="creating">Create</UButton>
        <UButton size="sm" variant="ghost" @click="cancelNewFolder">Cancel</UButton>
      </div>
    </div>
  </UFormField>
</template>

<script setup lang="ts">
import type { Folder } from '~/composables/useFileTree'

const props = defineProps<{
  modelValue: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const { folders, fetchFolders } = useFileTree()

const showNewFolderInput = ref(false)
const newFolderName = ref('')
const creating = ref(false)

// Get parent folder name for display when creating subfolder
const parentFolderName = computed(() => {
  if (!props.modelValue) return null
  const parent = folders.value.find(f => f.id === props.modelValue)
  return parent?.name || null
})

// Fetch folders on mount
onMounted(() => {
  if (folders.value.length === 0) {
    fetchFolders()
  }
})

const FOLDER_ROOT = '__root__' as const

interface FolderOption {
  label: string
  value: string
}

// Build hierarchical folder options
const folderOptions = computed((): FolderOption[] => {
  const options: FolderOption[] = [
    { label: 'Root (no folder)', value: FOLDER_ROOT },
    { label: '+ Create new folder...', value: '__new__' }
  ]

  // Build tree structure
  function addFolderWithChildren(folder: Folder, depth: number) {
    const indent = '\u00A0\u00A0'.repeat(depth)
    options.push({
      label: `${indent}${folder.name}`,
      value: folder.id
    })

    // Add children
    const children = folders.value.filter(f => f.parent_id === folder.id)
    children.sort((a, b) => a.name.localeCompare(b.name))
    for (const child of children) {
      addFolderWithChildren(child, depth + 1)
    }
  }

  // Start with root folders
  const rootFolders = folders.value.filter(f => f.parent_id === null)
  rootFolders.sort((a, b) => a.name.localeCompare(b.name))
  for (const folder of rootFolders) {
    addFolderWithChildren(folder, 0)
  }

  return options
})

const selectedValue = computed({
  get(): string {
    if (showNewFolderInput.value) return '__new__'
    return props.modelValue ?? FOLDER_ROOT
  },
  set(value: string) {
    if (value === '__new__') {
      showNewFolderInput.value = true
      newFolderName.value = ''
    } else {
      showNewFolderInput.value = false
      emit('update:modelValue', value === FOLDER_ROOT ? null : value)
    }
  }
})

async function createNewFolder() {
  if (!newFolderName.value.trim()) return

  creating.value = true
  try {
    // Create folder under the currently selected parent (or root if none)
    const parentId = props.modelValue || null
    const data = await $fetch<Folder>('/api/folders', {
      method: 'POST',
      body: { name: newFolderName.value.trim(), parent_id: parentId }
    })
    folders.value = [...folders.value, data]
    emit('update:modelValue', data.id)
    showNewFolderInput.value = false
    newFolderName.value = ''
  } catch (err) {
    console.error('Failed to create folder:', err)
  } finally {
    creating.value = false
  }
}

function cancelNewFolder() {
  showNewFolderInput.value = false
  newFolderName.value = ''
  emit('update:modelValue', null)
}
</script>
