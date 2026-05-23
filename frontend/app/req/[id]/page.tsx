"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ReqIdRedirect() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  useEffect(() => {
    if (params.id) router.replace(`/r/${params.id}`);
    else router.replace("/");
  }, [router, params.id]);
  return null;
}
