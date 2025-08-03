<template>

  <BNavbar
  v-b-color-mode="'primary'"
    variant="primary"
    style="padding-left: 2rem; padding-right: 2rem"
  >
    <BNavbarBrand href="#" variant="light">ImageExplorer</BNavbarBrand>
    <BNavForm>
      <BButton @click="openAddPage = true" variant="info" class="me-2">
        Add Folder
      </BButton>
    </BNavForm>
    <BNavForm class="ms-auto mb-2" >
      <BInputGroup
        prepend="Search"
        class="mt-3"
      >
        <BFormInput v-model="queryText" style="min-width: 5em;" @keyup.enter="fetchResults"/>
        
        <BDropdown
          split
          @split-click="fetchResults"
          text="Go"
          class="me-2"
          variant="info"
          auto-close="outside"
        >
          <BFormCheckbox
              v-for="(option, index) in queryOptions"
              :key="index"
              v-model="selectedQueryOptions"
              :value="option.value"
            >
              {{ option.text }}
          </BFormCheckbox>
          <BButton variant="primary" @click="openSelectQueryFolder = true">Folder</BButton>
        </BDropdown>
       <div style="min-width: 100%; padding-left: 1em; font-size: small;" class="text-white" @click="queryFolder = ''">{{ queryFolder }}</div>
      </BInputGroup>
       
    </BNavForm>
  </BNavbar>

  <BModal v-model="openAddPage" title="Add" @ok="addFolder">
    <div style="margin-bottom: 1em;">
      <BInputGroup
        prepend="Path"
        class="mt-3"
      >
        <BFormInput v-model="selectedFolder" placeholder="Path"/>
        <BButton v-if="isElectron" variant="primary" @click="selectFolder">Select</BButton>

      </BInputGroup>
    </div>
  </BModal>

  <BModal v-model="openSelectQueryFolder" title="Query Folder" @ok="setQueryFolder">
    <div style="margin-bottom: 1em;">
      <BInputGroup
        prepend="Path"
        class="mt-3"
      >
        <BFormInput v-model="selectedFolder" placeholder="Path"/>
        <BButton v-if="isElectron" variant="primary" @click="selectFolder">Select</BButton>

      </BInputGroup>
    </div>
  </BModal>

  <div class="page">
    <div v-if="results.length" class="directory-block">
      <h2 class="directory-title">Search Results</h2>
      <div class="gallery">
        <div v-for="(img, index) in results" :key="index" class="thumbnail" @click="openModal(img.full_path)">
          <img :src="getImageUrl(img.full_path)" />
        </div>
      </div>
    </div>

    <div
      v-for="(group, dirname) in groupedImages"
      :key="dirname"
      class="directory-block"
    >
      <h2 class="directory-title">📁 Folder {{ dirname }}</h2>
      <BButton variant="primary" @click="deleteFolder(dirname)">Delete Folder</BButton>
      <div class="gallery">
        <div
          v-for="(img, index) in group"
          :key="img.id"
          class="thumbnail"
          @click="openModal(img.full_path)"
        >
          <!-- User full_path for dev-->
          <img :src="getImageUrl(img.full_path)" />
        </div>
      </div>
    </div>

    <div v-if="showModal" class="modal" @click.self="closeModal">

      <img :src="getImageUrl(currentImage)" class="modal-image" />
      <BButton variant="primary" @click="openInfo" class="info-btn" size="sm" pill>!</BButton>
      <BButton variant="primary" @click="closeModal" class="close-btn" size="sm" pill>x</BButton>
      
      <BModal v-model="showInfo" title="Info" style="z-index:101"> 
        <p>Image Path: {{ currentImage }}</p>
      </BModal>
      
    </div>
  </div>
</template>


<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const images = ref([])
const showModal = ref(false)
const showInfo = ref(false)
const currentGroup = ref([])
const currentIndex = ref(0)
const show = ref(false)
const queryText = ref('')
const selectedFolder = ref('')
const results = ref([])
const currentImage = ref('')
const openAddPage = ref(false);
const isElectron = ref(false);
const queryFolder = ref('')
const openSelectQueryFolder = ref(false);

const queryOptions = [
  {text: 'Semantic Search', value: 'use_text_embed'},
  {text: 'Exact Match', value: 'use_bm25'},
  {text: 'Image Search', value: 'use_joint_embed'} ]

const selectedQueryOptions = ref(['use_text_embed', 'use_bm25', 'use_joint_embed'])

onMounted(() => {
  // The `electronAPI` object will exist on the window if in Electron.
  if (window.electronAPI) {
    isElectron.value = true;
  }
});

const getImageUrl = (path) => `http://127.0.0.1:8000/file?path=${encodeURIComponent(path)}`

// Group by directory_id
const groupedImages = computed(() => {
  const groups = {} 
  for (const img of images.value) {
    const full_path = img.full_path
    const dirPath = full_path.substring(0, full_path.lastIndexOf('/'))
    if (!groups[dirPath]) {
      groups[dirPath] = []
    }
    groups[dirPath].push(img)
  }
  return groups
})


const openModal = (full_path) => {
  currentImage.value = full_path
  showModal.value = true
}

const openInfo = () => {
  showInfo.value = true
}
const closeModal = () => {
  showModal.value = false
  showInfo.value = false
}

onMounted(async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/image')
    images.value = res.data
  } catch (err) {
    console.error('Failed to load images', err)
  }
})

const selectFolder = async () => {
  if (!isElectron.value) return

  try {
    const folderPath = await window.electronAPI.selectFolder()
    if (folderPath) {
      selectedFolder.value = folderPath
    }
  } catch (err) {
    console.error('Failed to select folder', err)
    alert('Failed to select folder. Check console for details.')
  }
}

const addFolder = async () => {
  if (!selectedFolder) return

  await axios.post('http://127.0.0.1:8000/watcher/add', null, {
    params: { path: selectedFolder.value }
  })
  alert(`Folder added: ${selectedFolder.value}`)
  selectedFolder = '' // Reset the input field
}

const setQueryFolder = async () => {
  if (!selectedFolder) return
  queryFolder.value = selectedFolder.value
  selectedFolder = '' // Reset the input field
}



const deleteFolder = async (folderPath) => {

  await axios.delete('http://127.0.0.1:8000/watcher/remove', {
    params: { path: folderPath , delete_images: true}
  })
  alert(`Folder removed: ${folderPath}`)
}

const fetchResults = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/api/query', {
      params: { 
        text: queryText.value, 
        use_text_embed : selectedQueryOptions.value.includes('use_text_embed'), 
        use_bm25 : selectedQueryOptions.value.includes('use_bm25'), 
        use_joint_embed : selectedQueryOptions.value.includes('use_joint_embed'),
        path: queryFolder.value == '' ? null : queryFolder.value
      }
    })
    results.value = res.data
  } catch (err) {
    console.error('Search failed', err)
    alert('Search failed. Check console for details.')
  }
}
</script>

<style scoped>
.directory-group {
  margin-bottom: 3rem;
}

.gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 1em;
}

.thumbnail img {
  width: 150px;
  height: 150px;
  object-fit: cover;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #ccc;
}


.modal {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.85);
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 100%;
  z-index: 100;
}
.modal-image {
  max-width: 90%;
  max-height: 90%;
  border-radius: 8px;
}

.close-btn {
  position: absolute;
  top: 20px;
  right: 30px;
  font-size: 2rem;
  background: none;
  border: none;
  color: white;
  cursor: pointer;
}

.info-btn {
  position: absolute;
  top: 20px;
  right: 80px;
  font-size: 2rem;
  background: none;
  border: none;
  color: white;
  cursor: pointer;
}


.directory-block {
  border: 2px solid #ddd;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 2rem;
  background-color: #f9f9f9;
}

.directory-title {
  font-size: 1.2rem;
  margin-bottom: 0.75rem;
  color: #333;
  font-weight: bold;
  word-break: break-all;
}


</style>
