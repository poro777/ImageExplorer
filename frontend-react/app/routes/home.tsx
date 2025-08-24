import { useState } from "react";
import type { Route } from "./+types/home";
import PrimarySearchAppBar from "~/appbar";
import GroupImages from "~/images";
import type { Image } from '~/images';
import Modal from "~/modal";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "New React Router App" },
    { name: "description", content: "Welcome to React Router!" },
  ];
}



export default function Home() {
  const [modalImage, setModalImage] = useState<Image | null>(null);


  return <div><PrimarySearchAppBar/>
    <div className="page">
      <GroupImages setModalImage={setModalImage} />
      <Modal image={modalImage} setModalImage={setModalImage}/>
    </div>
  </div>;
}
