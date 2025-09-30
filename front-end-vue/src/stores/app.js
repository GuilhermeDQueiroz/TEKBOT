import { defineStore } from "pinia";

export const useAppStore = defineStore('app', {
    state: () => {
        temaClaro: true
    },
    getters: {},
    actions: {
        trocarTema(){
            this.temaClaro = !this.temaClaro;
            console.log(this.temaClaro)
        }
    }
});