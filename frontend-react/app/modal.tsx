import type { Dispatch, SetStateAction } from "react";
import type { Image } from "./images";
import { getImageUrl } from "./images";
import { styled } from "@mui/material/styles";

const ModalView = styled('div')(({ theme }) => ({
    position: "fixed",
    inset: 0,
    backgroundColor: "#000000c4",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minWidth: 100,
    zIndex: 100
}))

const ModalImage = styled('img')(({ theme }) => ({
    maxWidth: "90%",
    maxHeight: "90%",
    borderRadius: 8,
}))


export default function Modal(props: { image: Image | null, setModalImage: Dispatch<SetStateAction<Image | null>> }) {
    if (!props.image) return <></>;

    const reset = (e: React.MouseEvent<HTMLDivElement>) => {
        // Check if the clicked element is the same as the one with the event listener
        if (e.target === e.currentTarget) {
            //console.log('Clicked on the parent container, not a child.');
            props.setModalImage(null);
        } else {
            //console.log('Clicked on a child element.');
        }
    };

    return <ModalView onClick={reset}>
        <ModalImage src={getImageUrl(props.image.full_path)} />
    </ModalView>
}