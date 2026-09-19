// Original MINEPX pixel assets. No external sprite or source-code reuse.
export const avatarColors:Record<string,string>={brass:'#d5ae5e',sage:'#82a88b',copper:'#ce8567',ice:'#7cabb9'};
export function drawMiner(ctx:CanvasRenderingContext2D, avatar:string, pose=0) {
 const rect=(x:number,y:number,w:number,h:number,c:string)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h);};
 const color=avatarColors[avatar]||avatarColors.brass;
 rect(6,28,22,3,'#11151aaa');
 rect(11,21,5,7,'#454b53');rect(20,21,5,7,'#454b53');
 rect(9,27+(pose===1?-1:0),8,3,'#242830');rect(19,27+(pose===2?-1:0),8,3,'#242830');
 rect(8,14,20,9,'#263740');rect(12,15,12,8,color);rect(16,15,3,9,'#3e4e53');
 rect(7,16,5,6,'#c59878');rect(25,15,4,6,'#c59878');
 rect(11,7,15,9,'#d5aa85');rect(12,13,13,4,'#6e574b');
 rect(21,9,3,3,'#1e2529');rect(16,10,2,2,'#1e2529');
 rect(11,3,14,6,color);rect(8,7,21,3,color);rect(13,2,10,2,color);
 rect(18,3,5,5,'#f8dda0');rect(19,4,3,3,'#fff4d7');
 rect(14,4,3,2,'#ffffff25');
}
export function minerTexture(avatar:string,pose=0) {
 const canvas=document.createElement('canvas');canvas.width=36;canvas.height=34;
 drawMiner(canvas.getContext('2d')!,avatar,pose);return canvas;
}