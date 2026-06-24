<template>
  <div class="space-y-3.5 animate-pulse">
    <!-- Auditor banner -->
    <div class="rounded-[18px] h-[150px]" style="background:linear-gradient(115deg,#2a2545,#3a2a6e)"></div>

    <!-- Funnel strip -->
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <div v-for="n in 5" :key="'f' + n" class="bg-white rounded-[14px] border border-line p-3.5 shadow-card">
        <div class="flex items-center gap-2"><div class="w-8 h-8 rounded-[10px] bg-app-warm"></div><div class="h-2.5 w-16 rounded-full bg-app-warm"></div></div>
        <div class="h-6 w-14 rounded bg-app-warm mt-2.5"></div>
        <div class="h-2.5 w-20 rounded-full bg-app-warm mt-2"></div>
      </div>
    </div>

    <!-- Hero row -->
    <div class="grid lg:grid-cols-2 gap-3.5">
      <div v-for="n in 2" :key="'h' + n" class="bg-white rounded-[16px] border border-line p-[17px] shadow-card h-[132px]">
        <div class="flex items-center gap-2"><div class="w-[26px] h-[26px] rounded-[8px] bg-app-warm"></div><div class="h-3 w-40 rounded-full bg-app-warm"></div></div>
        <div class="h-7 w-32 rounded bg-app-warm mt-3"></div>
        <div class="h-2.5 w-56 rounded-full bg-app-warm mt-3"></div>
      </div>
    </div>

    <!-- KPI row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="n in 4" :key="'k' + n" class="bg-white rounded-[16px] border border-line p-4 shadow-card">
        <div class="flex items-center justify-between"><div class="h-2.5 w-20 rounded-full bg-app-warm"></div><div class="w-8 h-8 rounded-[10px] bg-app-warm"></div></div>
        <div class="h-7 w-24 rounded bg-app-warm mt-3"></div>
        <div class="h-[26px] w-full rounded bg-app-warm/60 mt-3"></div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid lg:grid-cols-[1.5fr_1fr] gap-3.5">
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card h-[200px]"><div class="h-3 w-40 rounded-full bg-app-warm"></div><div class="h-24 w-full rounded bg-app-warm/60 mt-5"></div></div>
      <div class="bg-white rounded-[14px] border border-line p-[17px] shadow-card h-[200px]"><div class="h-3 w-32 rounded-full bg-app-warm"></div><div class="space-y-3 mt-5"><div v-for="n in 3" :key="'c' + n" class="h-2.5 w-full rounded-full bg-app-warm/60"></div></div></div>
    </div>
  </div>
</template>
