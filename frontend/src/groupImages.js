import { ref, shallowRef, onUnmounted, computed } from "vue";
import axios from 'axios'

export function groupImages() {
  const images = ref([]);
  const count = ref(0);

  function init(folders) {
    // Clear existing data
    images.value = [];


    for (const folder of folders) {
      const group = { dirname: folder.path, list: [] , initialized: false};
      images.value.push(group);
    }

    count.value = images.value.length;
  }

  function slice(start, end) {
    const values = images.value.slice(start, end);
    values.forEach(async group => {
      if (!group.initialized) {
        group.initialized = true;
        try {
          const res = await axios.get('http://127.0.0.1:8000/image/folder', {
            params: { path: group.dirname }
          })
          group.list = res.data;
        } catch (err) {
          console.error('Failed to load images', err)
          group.initialized = false; // Reset initialization on error
        }
      }
    })

    return values;
  }

  function insertOrUpdateImage(image) {
    const full_path = image.full_path;
    const dirPath = full_path.substring(0, full_path.lastIndexOf('/'));
    const group = images.value.find(g => g.dirname === dirPath);
    if (group) {
      const index = group.list.findIndex(img => img.full_path === full_path);
      if (index !== -1) {
        group.list[index] = image; // Update existing image
      } else {
        group.list.push(image); // Add new image
      }
    } else {
      images.value.push({ dirname: dirPath, list: [image] });
    }
  }

  async function updateDesc(full_path) {
    const dirPath = full_path.substring(0, full_path.lastIndexOf('/'));
    const group = images.value.find(g => g.dirname === dirPath);
    if (!group) {
      return
    }

    const index = group.list.findIndex(img => img.full_path === full_path);
    if (index === -1) {
      return;
    }

    const image = group.list[index];

    try {
      const id = image.id
      const res = await axios.get("http://127.0.0.1:8000/api/text", {
        params: { id: id }
      })
      image.desc = res.data[id].replace(/\\n/g, "\n")   // backend should return plain text or JSON {text: "..."}
    } catch (err) {
      console.error("Failed to fetch text:", err)
    }
  }

  function deleteImage(full_path) {
    const dirPath = full_path.substring(0, full_path.lastIndexOf('/'));
    const group = images.value.find(g => g.dirname === dirPath);
    if (group) {
      group.list = group.list.filter(img => img.full_path !== full_path);
      if (group.list.length === 0) {
        //images.value = images.value.filter(g => g.dirname !== dirPath);
      }
    }
  }

  function createDirectory(path) {
    const group = images.value.find(g => g.dirname === path);
    if (!group) {
      images.value.unshift({ dirname: path, list: [], initialized: false });
      count.value = images.value.length;
    }
  }

  function removeDirectory(path) {
    const index = images.value.findIndex(g => g.dirname === path);
    if (index !== -1) {
      images.value.splice(index, 1);
      count.value = images.value.length;
    }
  }


  return {images, count, init, insertOrUpdateImage, updateDesc,
    deleteImage, createDirectory, removeDirectory,slice};
}
