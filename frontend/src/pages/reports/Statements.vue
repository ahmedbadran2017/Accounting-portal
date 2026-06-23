<template>
  <div class="space-y-3.5">
    <div class="grid lg:grid-cols-3 gap-3.5">
      <div v-for="card in vm.cards" :key="card.key" class="bg-white rounded-card border border-line overflow-hidden">
        <div class="px-4 py-3 border-b border-line text-[13px] font-bold">{{ card.title }}</div>
        <table class="w-full text-[12px]">
          <tbody>
            <tr v-for="(row, i) in card.rows" :key="i" :class="row.kind === 'total' ? 'border-t border-line-2' : 'border-t border-line-hair'">
              <td class="px-4 py-2" :class="rowLabelClass(row.kind)">{{ row.label }}</td>
              <td class="px-4 py-2 text-end tnum" :class="rowValClass(row.kind)">{{ row.value }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="text-[11px] text-ink-muted flex items-center gap-1.5">
      <Icon name="alert" :size="13" color="#a8a29e" />{{ vm.note }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/Icon.vue";
import { statementsVM } from "@/data/statements";

const { locale } = useI18n();
const vm = computed(() => statementsVM(locale.value));

function rowLabelClass(kind) {
  if (kind === "total") return "font-bold text-ink";
  if (kind === "sub") return "text-ink-muted ps-6";
  return "text-ink-2";
}
function rowValClass(kind) {
  if (kind === "total") return "font-bold text-ink";
  if (kind === "pos") return "font-bold text-success-dark";
  if (kind === "sub") return "text-ink-muted";
  return "font-semibold text-ink";
}
</script>
