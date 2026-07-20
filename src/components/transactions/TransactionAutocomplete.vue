<template>
  <label class="autocomplete-field">
    <span class="field-label">{{ label }}</span>
    <span class="combobox" @focusout="scheduleClose">
      <input
        ref="inputElement"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :aria-expanded="open ? 'true' : 'false'"
        :aria-controls="listId"
        :aria-activedescendant="activeOptionId"
        role="combobox"
        autocomplete="off"
        @focus="openList"
        @input="onInput"
        @keydown="onKeydown"
      >
      <button
        v-if="modelValue && !disabled"
        class="clear-button"
        type="button"
        aria-label="Clear"
        @mousedown.prevent
        @click="clearValue"
      >
        ×
      </button>
      <ul v-if="open && visibleOptions.length" :id="listId" class="options" role="listbox">
        <li
          v-for="(option, index) in visibleOptions"
          :id="optionId(index)"
          :key="option.key"
          :class="{ active: index === activeIndex, create: option.create }"
          role="option"
          :aria-selected="index === activeIndex ? 'true' : 'false'"
          @mousedown.prevent="choose(option)"
          @mousemove="activeIndex = index"
        >
          <span>{{ option.label }}</span>
          <small v-if="option.secondary">{{ option.secondary }}</small>
        </li>
      </ul>
    </span>
  </label>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  selectedId: { type: [String, Number], default: null },
  items: { type: Array, default: () => [] },
  recentIds: { type: Array, default: () => [] },
  label: { type: String, required: true },
  placeholder: { type: String, default: '' },
  allowCreate: { type: Boolean, default: false },
  createLabel: { type: String, default: 'Create' },
  disabled: { type: Boolean, default: false },
  autofocus: { type: Boolean, default: false },
  maxResults: { type: Number, default: 60 },
})

const emit = defineEmits(['update:modelValue', 'select', 'create', 'clear'])
const inputElement = ref(null)
const open = ref(false)
const activeIndex = ref(0)
const listId = `transaction-autocomplete-${Math.random().toString(36).slice(2)}`

function normalize(value) {
  return String(value ?? '').normalize('NFKC').trim().replace(/\s+/gu, ' ').toLocaleLowerCase()
}

const sortedItems = computed(() => {
  const query = normalize(props.modelValue)
  const recentRank = new Map(props.recentIds.map((id, index) => [String(id), index]))
  return props.items
    .map((item, sourceIndex) => {
      const name = String(item.name ?? '')
      const normalized = normalize(name)
      const prefix = query && normalized.startsWith(query)
      const contains = query && normalized.includes(query)
      return {
        item,
        name,
        normalized,
        sourceIndex,
        matchRank: query ? (prefix ? 0 : contains ? 1 : 3) : 2,
        recentRank: recentRank.has(String(item.id)) ? recentRank.get(String(item.id)) : 100000,
      }
    })
    .filter(candidate => !query || candidate.matchRank < 3)
    .sort((left, right) => left.matchRank - right.matchRank
      || left.recentRank - right.recentRank
      || left.sourceIndex - right.sourceIndex)
})

const visibleOptions = computed(() => {
  const options = sortedItems.value.slice(0, props.maxResults).map(candidate => ({
    key: `item-${candidate.item.id}`,
    label: candidate.name,
    secondary: candidate.item.secondary ?? '',
    item: candidate.item,
    create: false,
  }))
  const query = String(props.modelValue ?? '').trim()
  const exact = props.items.some(item => normalize(item.name) === normalize(query))
  if (props.allowCreate && query && !exact) {
    options.push({
      key: `create-${query}`,
      label: `${props.createLabel} “${query}”`,
      secondary: '',
      item: null,
      create: true,
    })
  }
  return options
})

const activeOptionId = computed(() => open.value && visibleOptions.value.length
  ? optionId(activeIndex.value)
  : undefined)

watch(visibleOptions, options => {
  if (activeIndex.value >= options.length) activeIndex.value = Math.max(0, options.length - 1)
})

onMounted(() => {
  if (props.autofocus) nextTick(() => inputElement.value?.focus())
})

function optionId(index) {
  return `${listId}-option-${index}`
}

function openList() {
  if (props.disabled) return
  open.value = true
  const selectedIndex = visibleOptions.value.findIndex(option => String(option.item?.id) === String(props.selectedId))
  activeIndex.value = selectedIndex >= 0 ? selectedIndex : 0
}

function scheduleClose() {
  window.setTimeout(() => { open.value = false }, 100)
}

function onInput(event) {
  emit('update:modelValue', event.target.value)
  open.value = true
  activeIndex.value = 0
}

function clearValue() {
  emit('update:modelValue', '')
  emit('clear')
  open.value = true
  nextTick(() => inputElement.value?.focus())
}

function choose(option) {
  if (option.create) {
    emit('create', String(props.modelValue ?? '').trim())
  } else {
    emit('update:modelValue', option.item.name)
    emit('select', option.item)
  }
  open.value = false
}

function chooseExactOrActive() {
  const exact = visibleOptions.value.find(option => !option.create
    && normalize(option.item.name) === normalize(props.modelValue))
  choose(exact ?? visibleOptions.value[activeIndex.value])
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    openList()
    activeIndex.value = Math.min(activeIndex.value + 1, visibleOptions.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    openList()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (event.key === 'Enter' && open.value && visibleOptions.value.length) {
    event.preventDefault()
    chooseExactOrActive()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    open.value = false
  }
}
</script>

<style scoped>
.autocomplete-field { display: grid; gap: 6px; min-width: 0; }
.field-label { font-weight: 600; font-size: .92rem; }
.combobox { position: relative; display: block; }
.combobox input { width: 100%; min-height: 40px; padding-right: 34px; box-sizing: border-box; }
.clear-button { position: absolute; inset-inline-end: 6px; top: 5px; width: 30px; height: 30px; border: 0; background: transparent; font-size: 20px; cursor: pointer; }
.options { position: absolute; z-index: 1200; top: calc(100% + 4px); inset-inline: 0; max-height: min(320px, 45vh); overflow-y: auto; margin: 0; padding: 4px; list-style: none; border: 1px solid var(--color-border); border-radius: var(--border-radius-large); background: var(--color-main-background); box-shadow: 0 6px 24px rgb(0 0 0 / 18%); }
.options li { display: flex; justify-content: space-between; gap: 12px; min-height: 38px; padding: 8px 10px; border-radius: var(--border-radius); cursor: pointer; }
.options li.active { background: var(--color-primary-light); }
.options li.create { font-weight: 600; color: var(--color-primary-element); }
.options small { opacity: .65; white-space: nowrap; }
@media (max-width: 700px) {
  .combobox input { min-height: 46px; font-size: 16px; }
  .options { max-height: 44vh; }
  .options li { min-height: 46px; align-items: center; }
}
</style>
