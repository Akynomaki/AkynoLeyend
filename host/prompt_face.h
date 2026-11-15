/* Controller-name classification. Manual face selection takes priority. */
#pragma once
#include <ctype.h>
static inline int prompt_contains(const char *text,const char *word) {
    if(!text) return 0;
    for(;*text;++text) {
        unsigned i=0;
        while(word[i] && text[i] && tolower((unsigned char)text[i])==word[i]) ++i;
        if(!word[i]) return 1;
    }
    return 0;
}
static inline int prompt_face_for(int choice,const char *name,int xinput) {
    if(choice>=1 && choice<=HOS_PROMPT_N) return choice-1;
    if(prompt_contains(name,"dualsense") || prompt_contains(name,"ps5")) return HOS_PROMPT_PS5;
    if(prompt_contains(name,"dualshock") || prompt_contains(name,"ps4") || prompt_contains(name,"playstation")) return HOS_PROMPT_PS4;
    if(prompt_contains(name,"steam deck")) return HOS_PROMPT_STEAMDECK;
    if(prompt_contains(name,"nintendo") || prompt_contains(name,"switch") || prompt_contains(name,"joy-con")) return HOS_PROMPT_SWITCH;
    return (name && *name) || xinput ? HOS_PROMPT_XBOX : HOS_PROMPT_SWITCH;
}
