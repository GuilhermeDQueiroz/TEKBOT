<script setup>
</script>

<template>
  <head>
    <title>TekBot</title>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" />
  </head>
  <main>
    <router-view />
  </main>
</template>

<style scope>
@import url("https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&display=swap");

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0.8);
    opacity: 0.6;
  }

  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}
</style>
