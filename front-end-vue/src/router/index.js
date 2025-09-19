import { createRouter, createWebHistory } from 'vue-router'

import Login from '@/components/Login.vue'
import Chat from '@/components/Chat.vue'
import Cadastro from '@/components/Cadastro.vue'
import RecuperarSenha from '@/components/RecuperarSenha.vue'

const routes = [
    {
        path: '/',
        name: 'Login',
        component: Login
    },
    {
        path: '/chat',
        name: 'Chat',
        component: Chat
    },
    {
        path: '/cadastro',
        name: 'Cadastro',
        component: Cadastro
    },
    {
        path: '/recuperarSenha',
        name: 'RecuperarSenha',
        component: RecuperarSenha
    }
    /*
    {
      path: '/perfil/:id', // Exemplo de rota dinâmica com parâmetro
      name: 'Profile',
      component: Profile,
      props: true // Permite passar os parâmetros da rota como props para o componente
    },
    // Catch-all route para lidar com URLs que não correspondem a nenhuma rota definida
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: NotFound
    } */
]

const router = createRouter({
    // Histórico de navegação, use createWebHistory para um bom suporte em browsers modernos
    history: createWebHistory(),
    routes
})

export default router