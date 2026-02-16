<script setup>
import { useLayout } from '@/layout/composables/layout';
import { ref } from 'vue';

const { layoutState, isDesktop } = useLayout();

const props = defineProps({
    item: {
        type: Object,
        default: () => ({})
    },
    root: {
        type: Boolean,
        default: true
    },
});

const open = ref(false);

const itemClick = (event, item) => {
    if (item.disabled) {
        event.preventDefault();
        return;
    }

    if (item.command) {
        item.command({ originalEvent: event, item: item });
    }

    if (item.items) {
        open.value = !open.value;
    } else {
        layoutState.overlayMenuActive = false;
        layoutState.mobileMenuActive = false;
        layoutState.menuHoverActive = false;
    }
};
</script>

<template>
    <li :class="{ 'layout-root-menuitem': root, 'active-menuitem': open }">
        <div v-if="root && item.label && item.visible !== false" class="layout-menuitem-root-text">{{ item.label }}</div>
        <a v-if="(!item.to || item.items) && item.visible !== false" :href="item.url" @click="itemClick($event, item)" :class="item.class" :target="item.target" tabindex="0">
            <i :class="item.icon" class="layout-menuitem-icon" />
            <span class="layout-menuitem-text">{{ item.label }}</span>
            <i class="pi pi-fw pi-angle-down layout-submenu-toggler" v-if="item.items" />
        </a>
        <router-link v-if="item.to && !item.items && item.visible !== false" @click="itemClick($event, item)" exactActiveClass="active-route" :class="item.class" tabindex="0" :to="item.to">
            <i :class="item.icon" class="layout-menuitem-icon" />
            <span class="layout-menuitem-text">{{ item.label }}</span>
        </router-link>
        <Transition v-if="item.items && item.visible !== false" name="layout-submenu">
            <ul v-show="root ? true : open" class="layout-submenu">
                <app-menu-item v-for="child in item.items" :key="child.label + '_' + (child.to || '')" :item="child" :root="false" />
            </ul>
        </Transition>
    </li>
</template>
