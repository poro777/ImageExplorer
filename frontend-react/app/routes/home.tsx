import type { Route } from "./+types/home";
import PrimarySearchAppBar from "~/appbar";
import GroupImages from "~/images";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "New React Router App" },
    { name: "description", content: "Welcome to React Router!" },
  ];
}



export default function Home() {
  return <div><PrimarySearchAppBar/>
    <div className="page">
      <GroupImages />
    </div>
  </div>;
}
