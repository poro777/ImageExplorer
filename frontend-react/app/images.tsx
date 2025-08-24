import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import axios from 'axios'
import ImageList from '@mui/material/ImageList';
import ImageListItem from '@mui/material/ImageListItem';
import ImageListItemBar from '@mui/material/ImageListItemBar';
import ListSubheader from '@mui/material/ListSubheader';
import IconButton from '@mui/material/IconButton';
import InfoIcon from '@mui/icons-material/Info';
import { styled } from '@mui/material/styles';

export type Image = {
    id: number,
    filename: string,
    full_path : string,
    width: number
    height: number
    thumbnail_path: string | null
    directory_id: number
    last_modified: string
    file_size: number
}
type Folder = { dirname: string, list: Image[], initialized: boolean };

export const getImageUrl = (path: string) => `http://127.0.0.1:8000/file?path=${encodeURIComponent(path)}`
export const getThumbnailUrl = (path: string) => `http://127.0.0.1:8000/thumbnail/${encodeURIComponent(path)}`
export function getThumbnailSource(image: Image) {
  if (image.thumbnail_path) {
    return getThumbnailUrl(image.thumbnail_path);
  } else {
    return getImageUrl(image.full_path);
  }
}

const DirTitle = styled('h2')(({ theme }) => ({
  fontSize: '1.2rem',
  color: theme.palette.text.primary,
  fontWeight: 'bold',
  wordBreak: 'break-all',
  margin: 0
}));

const DirBolck = styled('div')(({ theme }) => ({
  border: '2px solid #ddd',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '2rem',
  backgroundColor: theme.palette.background.paper,
  overflow: 'auto',
  maxHeight: '450px'
}));


export function GroupImages(props: {setModalImage: Dispatch<SetStateAction<Image | null>>}) {
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
  
  return renderedGroups.map(images =><DirBolck key={images.dirname}>
    <DirTitle>Folder {images.dirname}</DirTitle>
    <ImageList cols={6}>
      {images.list.map((image) => (
        <ImageListItem key={image.thumbnail_path} onClick={()=>props.setModalImage(image)}>
          <img
            src={getThumbnailSource(image)}
            alt={image.filename}
            loading="lazy"
            className='thumbnail'
          />

        </ImageListItem>
      ))}
    </ImageList>
  </DirBolck>)
}

export function SearchResult(props: {results: Image[], setModalImage: Dispatch<SetStateAction<Image | null>>}){
    const results = props.results

    return <DirBolck>
    <DirTitle>Results: {results.length}</DirTitle>
    <ImageList cols={6}>
      {results.map((image) => (
        <ImageListItem key={image.thumbnail_path} onClick={()=>props.setModalImage(image)}>
          <img
            src={getThumbnailSource(image)}
            alt={image.filename}
            loading="lazy"
            className='thumbnail'
          />

        </ImageListItem>
      ))}
    </ImageList>
  </DirBolck> 
}