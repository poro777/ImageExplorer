<template>
  <BToastOrchestrator />

  <BNavbar
    v-b-color-mode="'light'"
    variant="primary"
    style="padding-left: 2rem; padding-right: 2rem"
  >
    <BNavbarBrand href="#" variant="light" style="margin-right: 3rem;">ImageExplorer</BNavbarBrand>
    <BButton @click="openAddPage = adder.status.value === 'done'" variant="info" class="me-2" 
      :loading="adder.status.value === 'processing'"
      :loading-text="adder.progress.value + `/` + adder.total.value">
      Add Folder
    </BButton>
   
    <BNavForm class="ms-auto mb-2">
      <div>
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
              switch
            >
              {{ option.text }}
          </BFormCheckbox>

          <BButton variant="outline-primary" @click="openSelectQueryFolder = true">📁</BButton>

        </BDropdown>
      </BInputGroup>
      <div class="text-white" style="text-align:right; cursor: pointer;" @click="queryFolder = ''">{{ queryFolder == ""? "All folders": queryFolder }}</div>
      </div>
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
    <div v-if="searched || isQuerying" class="directory-block">
      <h2 class="directory-title">Search Results: {{ results.length }}</h2>
      <div v-if="isQuerying">
        <BPlaceholder cols="7" animation="glow"/>
        <BPlaceholder width="65" animation="glow"/>
        <BPlaceholder cols="6" animation="glow"/>
      </div>
      <div v-else class="gallery">
        <div v-for="(img, index) in results" :key="index" class="thumbnail" @click="openModal(img)">
          <BImg v-if="img.thumbnail_path != null" lazy :src="getThumbnailUrl(img.thumbnail_path)"></BImg>
          <BImg v-else lazy :src="getImageUrl(img.full_path)"></BImg>
        </div>
      </div>
    </div>

    <b-pagination
            v-model="currentPage"
            :total-rows="groupedImages.count.value"
            :per-page="perPage"
            align="center"
    />

    <div
      v-for="(group, index) in groupedImages.slice((currentPage - 1) * perPage, currentPage * perPage)"
      :key="index" class="directory-block"
    >
      <div style="display: flex; align-items: center;">
      <BButton variant="light" @click="queryFolder=group.dirname">📁</BButton>
      <h2 class="directory-title" style="margin: 0;">Folder {{ group.dirname }}</h2>
      </div>
      <BButton variant="danger" @click="deleteFolder(group.dirname)">Delete Folder</BButton>
      <div class="gallery">
        <div
          v-for="(img, index) in group.list"
          :key="img.id"
          class="thumbnail"
          @click="openModal(img)"
        >
          <!-- Use full_path for dev-->
          <BImg v-if="img.thumbnail_path != null" lazy :src="getThumbnailUrl(img.thumbnail_path)"></BImg>
          <BImg v-else lazy :src="getImageUrl(img.full_path)"></BImg>
        </div>
      </div>
    </div>

    <div v-if="showModal" class="modal" @click.self="closeModal">

      <img :src="getImageUrl(currentImage.full_path)" class="modal-image" />
      <BButton variant="primary" @click="openInfo" class="info-btn" size="sm" pill>!</BButton>
      <BButton variant="primary" @click="closeModal" class="close-btn" size="sm" pill>x</BButton>
      
      <BModal v-model="showInfo" title="Info" style="z-index:101" size="lg" ok-only> 
        <BAccordion free>
          <BAccordionItem title="Image Path">
            {{ currentImage.full_path }}
          </BAccordionItem>
          <BAccordionItem title="Generated Description">
            <BButton variant="primary" @click.stop="regenDesc(currentImage.id)" size="sm" style="margin-left: 1em;">Re-Gen</BButton>
            <VMarkdownView 
              :mode="'light'"
              :content="currentImage.desc"
            ></VMarkdownView >
          </BAccordionItem>
        </BAccordion>

      </BModal>
      
    </div>
  </div>

    <div :class="'top-0 start-50 translate-middle-x'" class="toast-container position-fixed p-3">
      <BToast :show="watcherProcessing" no-close-button :show-on-pause="false">
        <template #title> Changes detected </template>
        <div style="min-width: 100%; display: flex; align-items: center; margin: auto;"> 
          <BSpinner label="Spinning"class="mx-1" />
          <div style="margin-left: 1em;"> Watching for changes... </div>
       </div>
        
      </BToast>
    </div>
</template>


<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import {folderAdder} from './watcher'
import { useToastController } from 'bootstrap-vue-next'
import { groupImages } from './groupImages'
import { VMarkdownView  } from 'vue3-markdown'
import 'vue3-markdown/dist/vue3-markdown.css'

const showModal = ref(false)
const showInfo = ref(false)
const queryText = ref('')
const selectedFolder = ref('')
const results = ref([])
const currentImage = ref('')
const openAddPage = ref(false);
const isElectron = ref(false);
const queryFolder = ref('');
const openSelectQueryFolder = ref(false)
const perPage = ref(4)
const currentPage = ref(1)

const isQuerying = ref(false)
const searched = ref(false)
const imageDesc = ref('')

let pageVisible = document.visibilityState === 'visible' ? true : false;

let adder = folderAdder()
let groupedImages = groupImages()

const {create} = useToastController()

const watcherProcessing = ref(false)

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
  document.addEventListener('visibilitychange', () => {
    pageVisible = document.visibilityState === 'visible' ? true : false;
  });
});

onMounted(async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/watcher/listening')

    let folders = res.data
    groupedImages.init(folders)
    
    
  } catch (err) {
    console.error('Failed to load images', err)
  }
})

const getImageUrl = (path) => `http://127.0.0.1:8000/file?path=${encodeURIComponent(path)}`
const getThumbnailUrl = (path) => `http://127.0.0.1:8000/thumbnail/${encodeURIComponent(path)}`


const openModal = (image) => {
  currentImage.value = image
  showModal.value = true
}

const openInfo = async () => {
  showInfo.value = true

  if(currentImage.value.desc == null || currentImage.value.desc == ''){
    groupedImages.updateDesc(currentImage.value.full_path)
  }
}
const closeModal = () => {
  showModal.value = false
  showInfo.value = false
}


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

  adder.start(selectedFolder.value)
 
  return;
  await axios.post('http://127.0.0.1:8000/watcher/add', null, {
    params: { path: selectedFolder.value }
  })
  alert(`Folder added: ${selectedFolder.value}`)
  selectedFolder.value = '' // Reset the input field
}

const setQueryFolder = async () => {
  if (!selectedFolder) return
  queryFolder.value = selectedFolder.value
  selectedFolder.value = '' // Reset the input field
}



const deleteFolder = async (folderPath) => {

  await axios.delete('http://127.0.0.1:8000/watcher/remove', {
    params: { path: folderPath , delete_images: true}
  })
  alert(`Folder removed: ${folderPath}`)
}

const fetchResults = async () => {
  try {
    if (!queryText.value.trim()) {
      results.value = []
      return
    }

    isQuerying.value = true
    const res = await axios.get('http://127.0.0.1:8000/api/query', {
      params: { 
        text: queryText.value, 
        use_text_embed : selectedQueryOptions.value.includes('use_text_embed'), 
        use_bm25 : selectedQueryOptions.value.includes('use_bm25'), 
        use_joint_embed : selectedQueryOptions.value.includes('use_joint_embed'),
        path: queryFolder.value == '' ? null : queryFolder.value
      }
    })
    isQuerying.value = false
    results.value = res.data
    searched.value = true

  } catch (err) {
    console.error('Search failed', err)
    alert('Search failed. Check console for details.')
  }
}

const regenDesc = async (id) => {
  const res = await axios.post('http://127.0.0.1:8000/image/regendesc', null, {
    params: { 
      id: id,
    }
  })
}

const source = new EventSource("http://127.0.0.1:8000/watcher/sse");
let isOpenOnce = false;
source.onopen = function() {
 if(isOpenOnce) {
  source.close();
 }else {
  console.log("Connection to server opened.");
  isOpenOnce = true;
 }
}
source.addEventListener("update", async  (event) => {
    const data = JSON.parse(event.data);
    watcherProcessing.value = true;

    // insert or update the image in the images array
    const res = await axios.get('http://127.0.0.1:8000/image/lookup', {
      params: { 
        file: data.path,
      }
    });

    groupedImages.insertOrUpdateImage(res.data);


    if(res.data.full_path == currentImage.value.full_path){
      currentImage.value = res.data
      groupedImages.updateDesc(res.data.full_path)
    }

    create?.({
        props: {
          title: 'Update',
          pos: 'middle-center',
          value: 10000,
          body: data.path,
        },
      })
});

source.addEventListener("delete", (event) => {
    const data = JSON.parse(event.data);
    watcherProcessing.value = true;
    // remove the image from the images array
    groupedImages.deleteImage(data.path);
    create?.({
        props: {
          title: 'Delete',
          pos: 'middle-center',
          value: 10000,
          body: data.path,
        },
      })
});

source.addEventListener("create", (event) => {
    const data = JSON.parse(event.data);
    groupedImages.createDirectory(data.dir);
    create?.({
        props: {
          title: 'CREATE FOLDER',
          pos: 'middle-center',
          value: 10000,
          body: data.dir,
        },
      })
});

source.addEventListener("remove", (event) => {
    const data = JSON.parse(event.data);
    groupedImages.removeDirectory(data.dir);
    create?.({
        props: {
          title: 'REMOVE FOLDER',
          pos: 'middle-center',
          value: 10000,
          body: data.dir,
        },
      })
});


source.addEventListener("start_processing", (event) => {
    watcherProcessing.value = true;
    console.log("start_processing")
});

source.addEventListener("stop_processing", (event) => {
    setTimeout(() => {
      watcherProcessing.value = false;
      console.log("stop_processing")
    }, 500);
    
});


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
  overflow: auto;
  max-height: 450px;
}

.directory-title {
  font-size: 1.2rem;
  color: #333;
  font-weight: bold;
  word-break: break-all;
}


</style>
