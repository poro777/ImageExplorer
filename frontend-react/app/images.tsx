import { useEffect, useState } from 'react';
import axios from 'axios'
import ImageList from '@mui/material/ImageList';
import ImageListItem from '@mui/material/ImageListItem';
import ImageListItemBar from '@mui/material/ImageListItemBar';
import ListSubheader from '@mui/material/ListSubheader';
import IconButton from '@mui/material/IconButton';
import InfoIcon from '@mui/icons-material/Info';


type Folder = { dirname: string, list: any[], initialized: boolean };


export default function GroupImages() {
  const [groupedImages, setGroup] = useState<Folder[]>([]);
  const [count, setcount] = useState(0);

  async function init() {
    const res = await axios.get('http://127.0.0.1:8000/watcher/listening')
    const folders = res.data

    // Clear existing data
    setGroup([]);


    for (const folder of folders) {
      let group = { dirname: folder.path, list: [], initialized: false };
      setGroup(prev => [...prev, group]);
    }

    setcount(folders.length);
  }
  useEffect(() => {
    init();
  }, []); // The empty dependency array ensures this effect runs only once.



  function slice(start: number, end: number) {
    const values = groupedImages.slice(start, end);
    values.forEach(group => {
      if (!group.initialized) {
        const updatedGroup = { ...group, initialized: true };
        setGroup(prev => prev.map(g => g.dirname === group.dirname ? updatedGroup : g))
        
        axios.get('http://127.0.0.1:8000/image/folder', {
          params: { path: group.dirname }
        }).then(res => {
          updatedGroup.list = res.data
          setGroup(prev => prev.map(g => g.dirname === group.dirname ? updatedGroup : g))
        })
        .catch(err => console.error('Failed to load images', err))

      }
    })
    return values;
  }

  const renderedGroups = slice(0, count);
  
  return renderedGroups.map(images =><div key={images.dirname}>
    {images.dirname}
    <ImageList cols={6}>
      {images.list.map((image) => (
        <ImageListItem key={image.thumbnail_path}>
          <img
            src={`http://127.0.0.1:8000/thumbnail/${encodeURIComponent(image.thumbnail_path)}`}
            alt={image.filename}
            loading="lazy"
            className='thumbnail'
          />

        </ImageListItem>
      ))}
    </ImageList>
  </div>)
}
