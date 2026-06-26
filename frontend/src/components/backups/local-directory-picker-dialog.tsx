"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, FolderOpen, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { backupsApi } from "@/lib/backups";
import { cn } from "@/lib/utils";

interface LocalDirectoryPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPath?: string;
  onSelect: (absolutePath: string) => void;
}

export function LocalDirectoryPickerDialog({
  open,
  onOpenChange,
  initialPath = "",
  onSelect,
}: LocalDirectoryPickerDialogProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [directories, setDirectories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await backupsApi.browseLocal(path);
      setCurrentPath(data.current_path);
      setParentPath(data.parent_path === data.current_path ? null : data.parent_path);
      setDirectories(data.directories);
    } catch {
      setError("Could not browse this folder");
      setDirectories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      load(initialPath);
    }
  }, [open, initialPath, load]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Select Backup Directory</DialogTitle>
          <DialogDescription className="font-mono text-xs break-all">
            {currentPath || "/"}
          </DialogDescription>
        </DialogHeader>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!parentPath || loading}
            onClick={() => parentPath != null && load(parentPath)}
          >
            <ChevronLeft className="h-4 w-4" />
            Up
          </Button>
          <Button
            type="button"
            variant="default"
            size="sm"
            className="ml-auto"
            onClick={() => {
              onSelect(currentPath);
              onOpenChange(false);
            }}
          >
            Use this folder
          </Button>
        </div>

        <ScrollArea className="h-64 rounded-lg border">
          <div className="p-1">
            {loading ? (
              <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </div>
            ) : directories.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">No subfolders</p>
            ) : (
              directories.map((dir) => {
                const childPath = currentPath.endsWith("/")
                  ? `${currentPath}${dir}`
                  : `${currentPath}/${dir}`;
                return (
                  <button
                    key={childPath}
                    type="button"
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
                    )}
                    onClick={() => load(childPath)}
                  >
                    <FolderOpen className="h-4 w-4 shrink-0 text-amber-500" />
                    <span className="truncate">{dir}</span>
                    <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground" />
                  </button>
                );
              })
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
